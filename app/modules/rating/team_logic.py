from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List, Dict, Tuple
from app.models.rating import TeamRating, TeamRatingLog, UserRating
from app.models.team import Team, TeamMember


class TeamRatingService:
    """Сервис для управления командным рейтингом"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_team_rating(self, team_id: int) -> TeamRating:
        """Получить или создать командный рейтинг"""
        result = await self.db.execute(
            select(TeamRating).where(TeamRating.team_id == team_id)
        )
        rating = result.scalar_one_or_none()

        if not rating:
            rating = TeamRating(team_id=team_id)
            self.db.add(rating)
            await self.db.flush()

        return rating

    async def recalculate_team_rating(self, team_id: int) -> TeamRating:
        """Пересчитать средний КРК команды"""
        # Получаем всех участников команды
        result = await self.db.execute(
            select(TeamMember)
            .where(TeamMember.team_id == team_id)
        )
        members = result.scalars().all()

        if not members:
            # Команда без участников
            team_rating = await self.get_or_create_team_rating(team_id)
            old_average = team_rating.average_krk
            old_count = team_rating.member_count

            team_rating.average_krk = 0.0
            team_rating.member_count = 0

            # Лог
            await self._log_change(
                team_rating=team_rating,
                old_average=old_average,
                new_average=0.0,
                old_count=old_count,
                new_count=0,
                event_type="no_members",
                description="Команда без участников"
            )

            return team_rating

        # Получаем рейтинги всех участников
        user_ids = [m.user_id for m in members]
        result = await self.db.execute(
            select(UserRating).where(UserRating.user_id.in_(user_ids))
        )
        user_ratings = {r.user_id: r.total_krk for r in result.scalars().all()}

        # Вычисляем среднее арифметическое
        total_krk = sum(user_ratings.get(uid, 0.0) for uid in user_ids)
        average_krk = total_krk / len(members) if members else 0.0

        team_rating = await self.get_or_create_team_rating(team_id)
        old_average = team_rating.average_krk
        old_count = team_rating.member_count

        team_rating.average_krk = average_krk
        team_rating.member_count = len(members)

        # Лог изменений
        await self._log_change(
            team_rating=team_rating,
            old_average=old_average,
            new_average=average_krk,
            old_count=old_count,
            new_count=len(members),
            event_type="recalculated",
            description=f"Пересчет КРК команды. Участников: {len(members)}"
        )

        return team_rating

    async def on_member_joined(
        self,
        team_id: int,
        user_id: int
    ) -> TeamRating:
        """Обработка вступления участника в команду"""
        # Пересчитываем рейтинг команды
        return await self.recalculate_team_rating(team_id)

    async def on_member_left(
        self,
        team_id: int,
        user_id: int
    ) -> TeamRating:
        """Обработка выхода участника из команды"""
        # Рейтинг пользователя переходит с ним, но команда пересчитывается
        return await self.recalculate_team_rating(team_id)

    async def on_member_rating_changed(
        self,
        team_id: int,
        user_id: int,
        old_krk: float,
        new_krk: float
    ) -> TeamRating:
        """Обработка изменения рейтинга участника команды"""
        # Быстрый пересчет без полного запроса
        team_rating = await self.get_or_create_team_rating(team_id)

        if team_rating.member_count > 0:
            delta = new_krk - old_krk
            team_rating.average_krk = team_rating.average_krk + (delta / team_rating.member_count)

            # Лог
            await self._log_change(
                team_rating=team_rating,
                old_average=team_rating.average_krk - (delta / team_rating.member_count),
                new_average=team_rating.average_krk,
                event_type="member_rating_changed",
                description=f"Изменение КРК участника {user_id}: {old_krk} -> {new_krk}",
                affected_user_id=user_id
            )

        return team_rating

    async def _log_change(
        self,
        team_rating: TeamRating,
        old_average: float,
        new_average: float,
        event_type: str,
        description: Optional[str] = None,
        old_count: Optional[int] = None,
        new_count: Optional[int] = None,
        affected_user_id: Optional[int] = None
    ):
        """Создать лог изменения командного рейтинга"""
        log = TeamRatingLog(
            team_rating_id=team_rating.id,
            team_id=team_rating.team_id,
            old_average=old_average,
            new_average=new_average,
            old_member_count=old_count,
            new_member_count=new_count,
            event_type=event_type,
            description=description,
            affected_user_id=affected_user_id
        )
        self.db.add(log)
        await self.db.flush()

    async def get_team_rankings(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[TeamRating], int]:
        """Получить рейтинг команд"""
        query = select(TeamRating).order_by(TeamRating.average_krk.desc())

        # Общее количество
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Пагинация
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        ratings = result.scalars().all()

        return list(ratings), total

    async def get_top_teams(self, limit: int = 10) -> List[TeamRating]:
        """Получить ТОП-N команд"""
        result = await self.db.execute(
            select(TeamRating)
            .order_by(TeamRating.average_krk.desc())
            .limit(limit)
        )
        return list(result.scalars().all())