from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from app.models.rating import (
    UserRating, RatingLog, RatingAdminOverwrite,
    TeamRating, TeamRatingLog, LeagueSettings, RatingPeriodArchive,
    LeagueTier
)
from app.models.team import Team, TeamMember
from app.models.user import User


class RatingService:
    """Сервис для управления индивидуальным рейтингом (КРК)"""

    # Формула КРК: Total = (Base × 0.6) + (Unity × 0.3) + (Bonus × 0.1) + Penalty
    BASE_WEIGHT = 0.6
    UNITY_WEIGHT = 0.3
    BONUS_WEIGHT = 0.1

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_krk(
        self,
        base: float,
        unity: float,
        bonus: float,
        penalty: float = 0.0
    ) -> float:
        """Расчет КРК по формуле"""
        return (base * self.BASE_WEIGHT) + (unity * self.UNITY_WEIGHT) + (bonus * self.BONUS_WEIGHT) + penalty

    async def get_or_create_user_rating(self, user_id: int) -> UserRating:
        """Получить или создать рейтинг пользователя"""
        result = await self.db.execute(
            select(UserRating).where(UserRating.user_id == user_id)
        )
        rating = result.scalar_one_or_none()

        if not rating:
            rating = UserRating(user_id=user_id)
            self.db.add(rating)
            await self.db.flush()

        return rating

    async def update_user_rating(
        self,
        user_id: int,
        base: Optional[float] = None,
        unity: Optional[float] = None,
        bonus: Optional[float] = None,
        penalty: Optional[float] = None,
        event_type: str = "activity",
        description: Optional[str] = None,
        team_id: Optional[int] = None,
        admin_user_id: Optional[int] = None
    ) -> UserRating:
        """Обновить рейтинг пользователя с логированием изменений"""
        rating = await self.get_or_create_user_rating(user_id)

        # Сохраняем старые значения
        old_base = rating.base_score
        old_unity = rating.unity_score
        old_bonus = rating.bonus_score
        old_penalty = rating.penalty_score
        old_total = rating.total_krk

        # Обновляем значения (если переданы)
        if base is not None:
            rating.base_score = base
        if unity is not None:
            rating.unity_score = unity
        if bonus is not None:
            rating.bonus_score = bonus
        if penalty is not None:
            rating.penalty_score = penalty

        # Пересчитываем итоговый КРК
        rating.total_krk = await self.calculate_krk(
            rating.base_score,
            rating.unity_score,
            rating.bonus_score,
            rating.penalty_score
        )

        # Определяем лигу
        rating.league = await self._get_league_for_score(rating.total_krk)

        # Создаем лог изменений
        log = RatingLog(
            user_id=user_id,
            old_base=old_base,
            new_base=rating.base_score,
            old_unity=old_unity,
            new_unity=rating.unity_score,
            old_bonus=old_bonus,
            new_bonus=rating.bonus_score,
            old_penalty=old_penalty,
            new_penalty=rating.penalty_score,
            old_total=old_total,
            new_total=rating.total_krk,
            event_type=event_type,
            description=description,
            team_id=team_id,
            admin_user_id=admin_user_id
        )
        self.db.add(log)

        await self.db.flush()
        return rating

    async def _get_league_for_score(self, score: float) -> str:
        """Определить лигу по баллу"""
        # Получаем настройки лиг из БД или используем дефолтные
        result = await self.db.execute(
            select(LeagueSettings).where(LeagueSettings.is_active == True)
        )
        settings = result.scalars().all()

        if settings:
            for setting in settings:
                if setting.max_score is None or score < setting.max_score:
                    if score >= setting.min_score:
                        return setting.tier
        else:
            # Дефолтные пороги
            if score >= 100:
                return LeagueTier.LEGEND.value
            elif score >= 50:
                return LeagueTier.PRO.value
            else:
                return LeagueTier.NEWBIE.value

        return LeagueTier.NEWBIE.value

    async def apply_penalty(
        self,
        user_id: int,
        penalty_amount: float,
        reason: str,
        admin_user_id: Optional[int] = None
    ) -> UserRating:
        """Применить штраф к пользователю"""
        rating = await self.get_or_create_user_rating(user_id)
        current_penalty = rating.penalty_score
        new_penalty = current_penalty - abs(penalty_amount)  # Штрафы отрицательные

        return await self.update_user_rating(
            user_id=user_id,
            penalty=new_penalty,
            event_type="penalty",
            description=f"Штраф: {reason}",
            admin_user_id=admin_user_id
        )

    async def admin_overwrite(
        self,
        user_id: int,
        admin_user_id: int,
        new_total: float,
        reason: str,
        base: Optional[float] = None,
        unity: Optional[float] = None,
        bonus: Optional[float] = None,
        penalty: Optional[float] = None
    ) -> UserRating:
        """Ручная корректировка КРК администратором (переопределение)"""
        rating = await self.get_or_create_user_rating(user_id)

        old_total = rating.total_krk

        # Если переданы компоненты, обновляем их
        if base is not None:
            rating.base_score = base
        if unity is not None:
            rating.unity_score = unity
        if bonus is not None:
            rating.bonus_score = bonus
        if penalty is not None:
            rating.penalty_score = penalty

        # Устанавливаем итоговый балл напрямую (переопределение формулы)
        rating.total_krk = new_total
        rating.league = await self._get_league_for_score(new_total)

        # Создаем запись о переопределении
        overwrite = RatingAdminOverwrite(
            user_id=user_id,
            admin_user_id=admin_user_id,
            new_base=base,
            new_unity=unity,
            new_bonus=bonus,
            new_penalty=penalty,
            new_total=new_total,
            reason=reason
        )
        self.db.add(overwrite)

        # Лог изменений
        log = RatingLog(
            user_id=user_id,
            old_total=old_total,
            new_total=new_total,
            event_type="admin_overwrite",
            description=f"Админ-корректировка: {reason}",
            admin_user_id=admin_user_id
        )
        self.db.add(log)

        await self.db.flush()
        return rating

    async def get_global_rankings(
        self,
        limit: int = 100,
        offset: int = 0,
        stream_id: Optional[int] = None,
        team_id: Optional[int] = None,
        league: Optional[str] = None
    ) -> Tuple[List[UserRating], int]:
        """Получить глобальный рейтинг с фильтрацией"""
        query = select(UserRating)

        # Фильтры
        if team_id:
            query = query.join(User).join(TeamMember).where(TeamMember.team_id == team_id)
        if league:
            query = query.where(UserRating.league == league)

        # Сортировка по убыванию КРК
        query = query.order_by(UserRating.total_krk.desc())

        # Общее количество
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Пагинация
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        ratings = result.scalars().all()

        return list(ratings), total

    async def get_user_rank_with_sticky(
        self,
        current_user_id: int,
        limit: int = 50
    ) -> Dict:
        """Получить рейтинг со sticky-позицией текущего пользователя"""
        # Получаем позицию текущего пользователя
        current_rating = await self.get_or_create_user_rating(current_user_id)

        # Подсчет позиции (сколько пользователей имеют больший КРК)
        result = await self.db.execute(
            select(func.count()).where(UserRating.total_krk > current_rating.total_krk)
        )
        current_rank = result.scalar() + 1

        # Получаем топ-N вокруг пользователя
        start_offset = max(0, current_rank - limit // 2)

        top_ratings, total = await self.get_global_rankings(
            limit=limit,
            offset=start_offset
        )

        return {
            "rankings": top_ratings,
            "current_user_rank": current_rank,
            "current_user_rating": current_rating,
            "total": total
        }

    async def update_rank_changes(self) -> None:
        """Обновить динамику позиций (сравнение с прошлой неделей)"""
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        # Получаем все рейтинги
        result = await self.db.execute(select(UserRating))
        all_ratings = result.scalars().all()

        for rating in all_ratings:
            # Находим позицию неделю назад в логах
            result = await self.db.execute(
                select(RatingLog)
                .where(RatingLog.user_id == rating.user_id)
                .where(RatingLog.created_at <= week_ago)
                .order_by(RatingLog.created_at.desc())
                .limit(1)
            )
            old_log = result.scalar_one_or_none()

            if old_log:
                # Сравниваем общую позицию (упрощенно)
                # В реальной системе нужно хранить snapshot рангов
                pass

            # Пока устанавливаем 0 (нет данных для сравнения)
            rating.rank_change = 0

        await self.db.flush()

    async def archive_period(self, year: int, month: int) -> int:
        """Архивировать рейтинги за период"""
        result = await self.db.execute(select(UserRating))
        all_ratings = result.scalars().all()

        archived_count = 0
        for rating in all_ratings:
            archive = RatingPeriodArchive(
                period_year=year,
                period_month=month,
                user_id=rating.user_id,
                final_krk=rating.total_krk,
                final_rank=rating.global_rank,
                league=rating.league
            )
            self.db.add(archive)
            archived_count += 1

        await self.db.flush()
        return archived_count