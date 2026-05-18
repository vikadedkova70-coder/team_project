import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func

# Импортируем ВСЕ модели перед созданием таблиц для корректной настройки relationships
from app.models.user import User, Student, UserRole
from app.models.team import Team, TeamMember, TeamInviteLink, TeamJoinRequest
from app.models.rating import (
    UserRating, RatingLog, RatingAdminOverwrite,
    TeamRating, TeamRatingLog, LeagueSettings, RatingPeriodArchive,
    LeagueTier
)
from app.modules.rating.logic import RatingService
from app.modules.rating.team_logic import TeamRatingService


# Тестовая БД в памяти
DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """Создание тестовой сессии БД"""
    engine = create_async_engine(DATABASE_URL, echo=False)

    # Создание таблиц
    async with engine.begin() as conn:
        from app.core.database import Base
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def rating_service(db_session):
    return RatingService(db_session)


@pytest.fixture
async def team_rating_service(db_session):
    return TeamRatingService(db_session)


@pytest.fixture
async def test_users(db_session):
    """Создание тестовых пользователей"""
    users = []
    students = []

    for i in range(1, 6):
        student = Student(surname=f"Testov{i}", name=f"Ivan{i}", patronymic=f"Ivanovich{i}")
        db_session.add(student)
        students.append(student)

    await db_session.flush()

    for i, student in enumerate(students, 1):
        user = User(
            username=f"user{i}",
            student_id=student.id,
            password_hash=f"hash{i}",
            role=UserRole.STUDENT.value
        )
        db_session.add(user)
        users.append(user)

    await db_session.flush()
    await db_session.commit()

    # Обновляем связи
    for user in users:
        await db_session.refresh(user)

    return users


@pytest.fixture
async def test_teams(db_session, test_users):
    """Создание тестовых команд"""
    teams = []

    for i in range(2):
        team = Team(
            name=f"Team{i+1}",
            description=f"Test team {i+1}",
            captain_id=test_users[i].id
        )
        db_session.add(team)
        teams.append(team)

    await db_session.flush()

    # Добавляем участников в команды
    # Team 1: user1, user2, user3
    for i in range(3):
        member = TeamMember(user_id=test_users[i].id, team_id=teams[0].id)
        db_session.add(member)

    # Team 2: user4, user5
    for i in range(3, 5):
        member = TeamMember(user_id=test_users[i].id, team_id=teams[1].id)
        db_session.add(member)

    await db_session.flush()
    await db_session.commit()

    return teams


class TestRatingCalculation:
    """Тесты расчета КРК"""

    @pytest.mark.asyncio
    async def test_krk_formula(self, rating_service):
        """Проверка формулы: Total = (Base×0.6) + (Unity×0.3) + (Bonus×0.1) + Penalty"""
        base, unity, bonus, penalty = 100.0, 80.0, 50.0, -10.0

        expected = (100 * 0.6) + (80 * 0.3) + (50 * 0.1) + (-10)
        expected = 60 + 24 + 5 - 10  # = 79

        result = await rating_service.calculate_krk(base, unity, bonus, penalty)

        assert abs(result - expected) < 0.01
        assert result == 79.0

    @pytest.mark.asyncio
    async def test_krk_no_penalty(self, rating_service):
        """КРК без штрафов"""
        result = await rating_service.calculate_krk(100.0, 100.0, 100.0, 0.0)
        assert result == 100.0

    @pytest.mark.asyncio
    async def test_krk_exceeds_100(self, rating_service):
        """КРК может превышать 100"""
        result = await rating_service.calculate_krk(150.0, 120.0, 100.0, 0.0)
        expected = (150 * 0.6) + (120 * 0.3) + (100 * 0.1)
        assert result == expected  # 90 + 36 + 10 = 136
        assert result > 100

    @pytest.mark.asyncio
    async def test_negative_krk_possible(self, rating_service):
        """Отрицательный КРК возможен при больших штрафах"""
        result = await rating_service.calculate_krk(10.0, 10.0, 10.0, -50.0)
        expected = (10 * 0.6) + (10 * 0.3) + (10 * 0.1) - 50
        expected = 6 + 3 + 1 - 50  # = -40
        assert result == -40.0


class TestUserRating:
    """Тесты индивидуального рейтинга"""

    @pytest.mark.asyncio
    async def test_create_user_rating(self, rating_service, test_users):
        """Создание рейтинга пользователя"""
        user = test_users[0]
        rating = await rating_service.get_or_create_user_rating(user.id)

        assert rating.user_id == user.id
        assert rating.base_score == 0.0
        assert rating.total_krk == 0.0
        assert rating.league == LeagueTier.NEWBIE.value

    @pytest.mark.asyncio
    async def test_update_user_rating(self, rating_service, test_users):
        """Обновление компонентов КРК"""
        user = test_users[0]

        rating = await rating_service.update_user_rating(
            user_id=user.id,
            base=100.0,
            unity=80.0,
            bonus=50.0,
            event_type="activity",
            description="Test update"
        )

        assert rating.base_score == 100.0
        assert rating.unity_score == 80.0
        assert rating.bonus_score == 50.0
        assert rating.penalty_score == 0.0
        # (100×0.6) + (80×0.3) + (50×0.1) = 60 + 24 + 5 = 89
        assert rating.total_krk == 89.0
        assert rating.league == LeagueTier.PRO.value

    @pytest.mark.asyncio
    async def test_apply_penalty(self, rating_service, test_users):
        """Применение штрафа"""
        user = test_users[0]

        # Сначала установим рейтинг
        await rating_service.update_user_rating(
            user_id=user.id,
            base=100.0,
            unity=100.0,
            bonus=100.0
        )

        # Применяем штраф
        rating = await rating_service.apply_penalty(
            user_id=user.id,
            penalty_amount=30.0,
            reason="Нарушение правил",
            admin_user_id=user.id
        )

        assert rating.penalty_score == -30.0
        assert rating.total_krk == 70.0  # 100 - 30

    @pytest.mark.asyncio
    async def test_admin_overwrite(self, rating_service, test_users):
        """Ручная корректировка администратором"""
        user = test_users[0]

        # Устанавливаем начальный рейтинг
        await rating_service.update_user_rating(
            user_id=user.id,
            base=50.0,
            unity=50.0,
            bonus=50.0
        )

        # Админ переопределяет
        rating = await rating_service.admin_overwrite(
            user_id=user.id,
            admin_user_id=user.id,
            new_total=150.0,
            reason="Исключительные заслуги"
        )

        assert rating.total_krk == 150.0
        assert rating.league == LeagueTier.LEGEND.value

        # Проверяем, что запись о переопределении создана
        result = await rating_service.db.execute(
            select(RatingAdminOverwrite).where(RatingAdminOverwrite.user_id == user.id)
        )
        overwrite = result.scalar_one_or_none()
        assert overwrite is not None
        assert overwrite.new_total == 150.0

    @pytest.mark.asyncio
    async def test_rating_history_logged(self, rating_service, test_users):
        """Логирование изменений рейтинга"""
        user = test_users[0]

        await rating_service.update_user_rating(
            user_id=user.id,
            base=100.0,
            event_type="challenge",
            description="Completed challenge"
        )

        result = await rating_service.db.execute(
            select(RatingLog).where(RatingLog.user_id == user.id)
        )
        logs = result.scalars().all()

        assert len(logs) >= 1
        assert logs[-1].event_type == "challenge"
        assert logs[-1].new_base == 100.0


class TestLeagueSystem:
    """Тесты системы лиг"""

    @pytest.mark.asyncio
    async def test_league_newbie(self, rating_service, test_users):
        """Лига Новичок: 0-49.99"""
        user = test_users[0]

        rating = await rating_service.update_user_rating(
            user_id=user.id,
            base=40.0,
            unity=40.0,
            bonus=40.0
        )
        # 24 + 12 + 4 = 40

        assert rating.league == LeagueTier.NEWBIE.value

    @pytest.mark.asyncio
    async def test_league_pro(self, rating_service, test_users):
        """Лига Профи: 50-99.99"""
        user = test_users[0]

        rating = await rating_service.update_user_rating(
            user_id=user.id,
            base=83.34,  # ~50/0.6
            unity=0.0,
            bonus=0.0
        )

        assert rating.league == LeagueTier.PRO.value

    @pytest.mark.asyncio
    async def test_league_legend(self, rating_service, test_users):
        """Лига Легенда: 100+"""
        user = test_users[0]

        rating = await rating_service.update_user_rating(
            user_id=user.id,
            base=100.0,
            unity=100.0,
            bonus=100.0
        )

        assert rating.league == LeagueTier.LEGEND.value

    @pytest.mark.asyncio
    async def test_league_demotion(self, rating_service, test_users):
        """Понижение в лиге при падении рейтинга"""
        user = test_users[0]

        # Сначала Легенда
        rating = await rating_service.update_user_rating(
            user_id=user.id,
            base=100.0,
            unity=100.0,
            bonus=100.0
        )
        assert rating.league == LeagueTier.LEGEND.value

        # Применяем большой штраф
        rating = await rating_service.apply_penalty(
            user_id=user.id,
            penalty_amount=60.0,
            reason="Demotion test"
        )

        # Должен упасть в Профи или Новичок
        assert rating.total_krk < 100.0
        assert rating.league != LeagueTier.LEGEND.value


class TestTeamRating:
    """Тесты командного рейтинга"""

    @pytest.mark.asyncio
    async def test_team_rating_average(self, team_rating_service, test_teams, test_users, db_session):
        """Командный КРК как среднее арифметическое"""
        team = test_teams[0]  # 3 участника

        # Устанавливаем рейтинги участникам
        rating_service = RatingService(db_session)
        await rating_service.update_user_rating(user_id=test_users[0].id, base=100.0, unity=0, bonus=0)  # 60
        await rating_service.update_user_rating(user_id=test_users[1].id, base=50.0, unity=0, bonus=0)   # 30
        await rating_service.update_user_rating(user_id=test_users[2].id, base=83.34, unity=0, bonus=0)  # ~50

        await db_session.commit()

        # Пересчитываем командный рейтинг
        team_rating = await team_rating_service.recalculate_team_rating(team.id)

        # Среднее: (60 + 30 + 50) / 3 = 46.67
        expected_avg = (60.0 + 30.0 + 50.0) / 3
        assert abs(team_rating.average_krk - expected_avg) < 0.1
        assert team_rating.member_count == 3

    @pytest.mark.asyncio
    async def test_member_joined_updates_team(self, team_rating_service, test_teams, test_users, db_session):
        """Вступление участника обновляет командный рейтинг"""
        team = test_teams[1]  # 2 участника: user4, user5

        # Используем пользователя, который ещё не в команде (user3 из Team 1)
        # Сначала устанавливаем ему рейтинг
        rating_service = RatingService(db_session)
        await rating_service.update_user_rating(user_id=test_users[2].id, base=150.0, unity=0, bonus=0)
        await db_session.commit()

        # Изначальный рейтинг команды 2
        initial = await team_rating_service.recalculate_team_rating(team.id)
        initial_avg = initial.average_krk

        # Добавляем пользователя user3 в команду 2
        # Сначала удаляем из текущей команды (Team 1)
        result = await db_session.execute(
            select(TeamMember).where(TeamMember.user_id == test_users[2].id)
        )
        current_membership = result.scalar_one()
        await db_session.delete(current_membership)
        await db_session.commit()

        # Теперь добавляем в новую команду
        new_member = TeamMember(user_id=test_users[2].id, team_id=team.id)
        db_session.add(new_member)
        await db_session.commit()

        # Пересчитываем
        updated = await team_rating_service.on_member_joined(team.id, test_users[2].id)

        assert updated.member_count == 3

    @pytest.mark.asyncio
    async def test_member_left_updates_team(self, team_rating_service, test_teams, test_users, db_session):
        """Выход участника обновляет командный рейтинг"""
        team = test_teams[0]  # 3 участника

        # Удаляем участника
        result = await db_session.execute(
            select(TeamMember).where(TeamMember.user_id == test_users[2].id)
        )
        member = result.scalar_one()
        await db_session.delete(member)
        await db_session.commit()

        # Пересчитываем
        updated = await team_rating_service.on_member_left(team.id, test_users[2].id)

        assert updated.member_count == 2

    @pytest.mark.asyncio
    async def test_member_rating_change_affects_team(self, team_rating_service, test_teams, test_users, db_session):
        """Изменение рейтинга участника влияет на команду"""
        team = test_teams[1]

        # Устанавливаем рейтинги
        rating_service = RatingService(db_session)
        r1 = await rating_service.update_user_rating(user_id=test_users[3].id, base=100.0, unity=0, bonus=0)  # 60
        r2 = await rating_service.update_user_rating(user_id=test_users[4].id, base=100.0, unity=0, bonus=0)  # 60
        await db_session.commit()

        # Командный: (60+60)/2 = 60
        team_rating = await team_rating_service.recalculate_team_rating(team.id)
        initial_avg = team_rating.average_krk
        assert abs(initial_avg - 60.0) < 0.1

        # Изменяем рейтинг одного участника
        new_rating = await rating_service.update_user_rating(
            user_id=test_users[3].id,
            base=200.0,  # Теперь 120
            unity=0,
            bonus=0
        )
        await db_session.commit()

        # Быстрое обновление
        updated = await team_rating_service.on_member_rating_changed(
            team.id, test_users[3].id, old_krk=60.0, new_krk=120.0
        )

        # Новый средний: (120+60)/2 = 90
        assert abs(updated.average_krk - 90.0) < 0.1


class TestLeaderboard:
    """Тесты лидербордов"""

    @pytest.mark.asyncio
    async def test_global_ranking_order(self, rating_service, test_users, db_session):
        """Глобальный рейтинг сортируется по убыванию КРК"""
        # Устанавливаем разные рейтинги для всех 5 пользователей
        for i, user in enumerate(test_users):
            await rating_service.update_user_rating(
                user_id=user.id,
                base=(i + 1) * 20,
                unity=0,
                bonus=0
            )
        await db_session.commit()

        rankings, total = await rating_service.get_global_rankings(limit=10)

        assert total == 5
        assert len(rankings) == 5
        # Первый должен быть с наибольшим КРК
        assert rankings[0].total_krk >= rankings[1].total_krk

    @pytest.mark.asyncio
    async def test_top_users_widget(self, rating_service, test_users, db_session):
        """Виджет ТОП-N пользователей"""
        for i, user in enumerate(test_users):
            await rating_service.update_user_rating(
                user_id=user.id,
                base=(i + 1) * 20,
                unity=0,
                bonus=0
            )
        await db_session.commit()

        rankings, _ = await rating_service.get_global_rankings(limit=3)

        assert len(rankings) == 3

    @pytest.mark.asyncio
    async def test_filter_by_league(self, rating_service, test_users, db_session):
        """Фильтрация по лиге"""
        # Создаем пользователей в разных лигах
        await rating_service.update_user_rating(user_id=test_users[0].id, base=10.0, unity=0, bonus=0)  # Newbie
        await rating_service.update_user_rating(user_id=test_users[1].id, base=100.0, unity=0, bonus=0)  # Pro/Legend
        await db_session.commit()

        newbie_rankings, _ = await rating_service.get_global_rankings(league="newbie")

        assert len(newbie_rankings) >= 1
        assert all(r.league == "newbie" for r in newbie_rankings)


class TestRatingTransfer:
    """Тесты перехода между командами"""

    @pytest.mark.asyncio
    async def test_rating_transfers_with_user(self, rating_service, team_rating_service, test_users, test_teams, db_session):
        """Рейтинг пользователя переходит с ним при смене команды"""
        user = test_users[0]

        # Устанавливаем рейтинг пользователю
        rating = await rating_service.update_user_rating(
            user_id=user.id,
            base=100.0,
            unity=80.0,
            bonus=50.0
        )
        initial_krk = rating.total_krk
        # (100×0.6) + (80×0.3) + (50×0.1) = 60 + 24 + 5 = 89
        assert initial_krk == 89.0

        # Пользователь уже в Team 1, добавляем его в Team 2
        # Сначала удаляем из текущей команды
        result = await db_session.execute(
            select(TeamMember).where(TeamMember.user_id == user.id)
        )
        current_membership = result.scalar_one()
        old_team_id = current_membership.team_id

        await db_session.delete(current_membership)
        await db_session.commit()

        # Старая команда пересчитывается
        await team_rating_service.on_member_left(old_team_id, user.id)

        # Добавляем в новую команду
        new_member = TeamMember(user_id=user.id, team_id=test_teams[1].id)
        db_session.add(new_member)
        await db_session.commit()

        # Рейтинг пользователя не изменился
        new_rating = await rating_service.get_or_create_user_rating(user.id)
        assert new_rating.total_krk == initial_krk

        # Новая команда пересчитывается с учетом нового участника
        await team_rating_service.on_member_joined(test_teams[1].id, user.id)


class TestArchiving:
    """Тесты архивации периодов"""

    @pytest.mark.asyncio
    async def test_archive_period(self, rating_service, test_users, db_session):
        """Архивация рейтингов за период"""
        # Устанавливаем рейтинги
        for user in test_users:
            await rating_service.update_user_rating(
                user_id=user.id,
                base=50.0 + user.id * 10,
                unity=0,
                bonus=0
            )
        await db_session.commit()

        # Архивируем
        count = await rating_service.archive_period(2024, 1)

        assert count == 5

        # Проверяем архив
        result = await db_session.execute(
            select(RatingPeriodArchive)
            .where(RatingPeriodArchive.period_year == 2024)
            .where(RatingPeriodArchive.period_month == 1)
        )
        archives = result.scalars().all()

        assert len(archives) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])