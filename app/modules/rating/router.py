from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.team import Team
from app.models.rating import RatingLog, RatingPeriodArchive, UserRating
from app.modules.rating.logic import RatingService
from app.modules.rating.team_logic import TeamRatingService
from app.modules.rating.schemas import (
    RatingUpdateRequest, PenaltyRequest, AdminOverwriteRequest,
    RatingResponse, LeaderboardResponse, TopUsersResponse,
    TeamLeaderboardResponse, LeagueDistributionResponse,
    RatingHistoryResponse, PeriodArchiveRequest, PeriodArchiveResponse,
    RankingItemResponse, TeamRatingResponse
)

router = APIRouter(prefix="/rating", tags=["Rating"])


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    team_id: Optional[int] = None,
    league: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить глобальный лидерборд пользователей.

    - **limit**: Количество записей (1-200)
    - **offset**: Смещение для пагинации
    - **team_id**: Фильтр по команде
    - **league**: Фильтр по лиге (newbie, pro, legend)

    Возвращает рейтинг со sticky-позицией текущего пользователя.
    """
    rating_service = RatingService(db)

    # Получаем рейтинг текущего пользователя
    current_rating = await rating_service.get_or_create_user_rating(current_user.id)

    # Получаем лидерборд с фильтрацией
    ratings, total = await rating_service.get_global_rankings(
        limit=limit,
        offset=offset,
        team_id=team_id,
        league=league
    )

    # Формируем ответ с username и team_name
    rankings = []
    for r in ratings:
        user_result = await db.execute(
            select(User).where(User.id == r.user_id)
        )
        user = user_result.scalar_one_or_none()
        username = user.username if user else "Unknown"

        # Получаем команду
        team_name = None
        if user and user.team_membership:
            team_result = await db.execute(
                select(Team).where(Team.id == user.team_membership.team_id)
            )
            team = team_result.scalar_one_or_none()
            team_name = team.name if team else None

        rankings.append(RankingItemResponse(
            user_id=r.user_id,
            username=username,
            total_krk=r.total_krk,
            global_rank=r.global_rank,
            league=r.league,
            rank_change=r.rank_change,
            team_name=team_name
        ))

    return LeaderboardResponse(
        rankings=rankings,
        current_user_rank=current_rating.global_rank,
        current_user_rating=RatingResponse(
            user_id=current_rating.user_id,
            base_score=current_rating.base_score,
            unity_score=current_rating.unity_score,
            bonus_score=current_rating.bonus_score,
            penalty_score=current_rating.penalty_score,
            total_krk=current_rating.total_krk,
            global_rank=current_rating.global_rank,
            league=current_rating.league,
            rank_change=current_rating.rank_change,
            updated_at=current_rating.updated_at
        ),
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/top-users", response_model=TopUsersResponse)
async def get_top_users(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Получить ТОП-N пользователей (виджет)"""
    rating_service = RatingService(db)
    ratings, _ = await rating_service.get_global_rankings(limit=limit)

    users = []
    for r in ratings:
        user_result = await db.execute(select(User).where(User.id == r.user_id))
        user = user_result.scalar_one_or_none()
        username = user.username if user else "Unknown"

        users.append(RankingItemResponse(
            user_id=r.user_id,
            username=username,
            total_krk=r.total_krk,
            global_rank=r.global_rank,
            league=r.league,
            rank_change=r.rank_change
        ))

    return TopUsersResponse(users=users)


@router.get("/top-teams", response_model=TeamLeaderboardResponse)
async def get_top_teams(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Получить ТОП-N команд (виджет)"""
    team_service = TeamRatingService(db)
    team_ratings = await team_service.get_top_teams(limit=limit)

    teams = []
    for tr in team_ratings:
        team_result = await db.execute(select(Team).where(Team.id == tr.team_id))
        team = team_result.scalar_one_or_none()
        team_name = team.name if team else "Unknown"

        teams.append(TeamRatingResponse(
            team_id=tr.team_id,
            team_name=team_name,
            average_krk=tr.average_krk,
            member_count=tr.member_count,
            global_rank=tr.global_rank,
            rank_change=tr.rank_change
        ))

    _, total = await team_service.get_team_rankings()

    return TeamLeaderboardResponse(teams=teams, total=total)


@router.get("/my-rating", response_model=RatingResponse)
async def get_my_rating(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить свой текущий рейтинг"""
    rating_service = RatingService(db)
    rating = await rating_service.get_or_create_user_rating(current_user.id)

    return RatingResponse(
        user_id=rating.user_id,
        base_score=rating.base_score,
        unity_score=rating.unity_score,
        bonus_score=rating.bonus_score,
        penalty_score=rating.penalty_score,
        total_krk=rating.total_krk,
        global_rank=rating.global_rank,
        league=rating.league,
        rank_change=rating.rank_change,
        updated_at=rating.updated_at
    )


@router.post("/update", response_model=RatingResponse)
async def update_rating(
    data: RatingUpdateRequest,
    target_user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить компоненты КРК пользователя.

    Требуются права администратора или модератора.
    """
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Требуемые права: admin или teacher")

    rating_service = RatingService(db)

    rating = await rating_service.update_user_rating(
        user_id=target_user_id,
        base=data.base,
        unity=data.unity,
        bonus=data.bonus,
        penalty=data.penalty,
        description=data.description,
        admin_user_id=current_user.id if current_user.role == "admin" else None
    )

    return RatingResponse(
        user_id=rating.user_id,
        base_score=rating.base_score,
        unity_score=rating.unity_score,
        bonus_score=rating.bonus_score,
        penalty_score=rating.penalty_score,
        total_krk=rating.total_krk,
        global_rank=rating.global_rank,
        league=rating.league,
        rank_change=rating.rank_change,
        updated_at=rating.updated_at
    )


@router.post("/penalty", response_model=RatingResponse)
async def apply_penalty(
    data: PenaltyRequest,
    target_user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Применить штраф к пользователю"""
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Требуемые права: admin или teacher")

    rating_service = RatingService(db)

    rating = await rating_service.apply_penalty(
        user_id=target_user_id,
        penalty_amount=data.amount,
        reason=data.reason,
        admin_user_id=current_user.id
    )

    return RatingResponse(
        user_id=rating.user_id,
        base_score=rating.base_score,
        unity_score=rating.unity_score,
        bonus_score=rating.bonus_score,
        penalty_score=rating.penalty_score,
        total_krk=rating.total_krk,
        global_rank=rating.global_rank,
        league=rating.league,
        rank_change=rating.rank_change,
        updated_at=rating.updated_at
    )


@router.post("/admin-overwrite", response_model=RatingResponse)
async def admin_overwrite_rating(
    data: AdminOverwriteRequest,
    target_user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Ручная корректировка КРК администратором (переопределение формулы).

    Позволяет установить итоговый балл напрямую, в обход автоматической формулы.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")

    rating_service = RatingService(db)

    rating = await rating_service.admin_overwrite(
        user_id=target_user_id,
        admin_user_id=current_user.id,
        new_total=data.new_total,
        reason=data.reason,
        base=data.base,
        unity=data.unity,
        bonus=data.bonus,
        penalty=data.penalty
    )

    return RatingResponse(
        user_id=rating.user_id,
        base_score=rating.base_score,
        unity_score=rating.unity_score,
        bonus_score=rating.bonus_score,
        penalty_score=rating.penalty_score,
        total_krk=rating.total_krk,
        global_rank=rating.global_rank,
        league=rating.league,
        rank_change=rating.rank_change,
        updated_at=rating.updated_at
    )


@router.get("/history/{user_id}", response_model=RatingHistoryResponse)
async def get_rating_history(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить историю изменений рейтинга пользователя"""
    # Проверка прав (только админ или сам пользователь)
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Нет доступа к истории")

    result = await db.execute(
        select(RatingLog)
        .where(RatingLog.user_id == user_id)
        .order_by(RatingLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    logs = result.scalars().all()

    # Общее количество
    count_result = await db.execute(
        select(func.count()).select_from(select(RatingLog).where(RatingLog.user_id == user_id).subquery())
    )
    total = count_result.scalar()

    history_items = []
    for log in logs:
        admin_username = None
        if log.admin_user_id:
            admin_result = await db.execute(select(User).where(User.id == log.admin_user_id))
            admin = admin_result.scalar_one_or_none()
            admin_username = admin.username if admin else None

        history_items.append(RatingHistoryItem(
            id=log.id,
            event_type=log.event_type,
            old_total=log.old_total,
            new_total=log.new_total,
            description=log.description,
            created_at=log.created_at,
            admin_username=admin_username
        ))

    return RatingHistoryResponse(user_id=user_id, logs=history_items, total=total)


@router.get("/league-distribution", response_model=LeagueDistributionResponse)
async def get_league_distribution(
    db: AsyncSession = Depends(get_db)
):
    """Получить распределение пользователей по лигам"""
    newbie = await db.execute(select(func.count()).where(UserRating.league == "newbie"))
    pro = await db.execute(select(func.count()).where(UserRating.league == "pro"))
    legend = await db.execute(select(func.count()).where(UserRating.league == "legend"))

    return LeagueDistributionResponse(
        newbie_count=newbie.scalar(),
        pro_count=pro.scalar(),
        legend_count=legend.scalar()
    )


@router.post("/archive-period", response_model=PeriodArchiveResponse)
async def archive_period(
    data: PeriodArchiveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Архивировать рейтинги за указанный период (месяц)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")

    rating_service = RatingService(db)
    archived_count = await rating_service.archive_period(data.year, data.month)

    return PeriodArchiveResponse(
        period_year=data.year,
        period_month=data.month,
        archived_count=archived_count
    )


@router.get("/archive/{year}/{month}")
async def get_archived_period(
    year: int,
    month: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Получить архив рейтингов за указанный период"""
    result = await db.execute(
        select(RatingPeriodArchive)
        .where(RatingPeriodArchive.period_year == year)
        .where(RatingPeriodArchive.period_month == month)
        .order_by(RatingPeriodArchive.final_krk.desc())
        .offset(offset)
        .limit(limit)
    )
    archives = result.scalars().all()

    # Общее количество
    count_result = await db.execute(
        select(func.count())
        .where(RatingPeriodArchive.period_year == year)
        .where(RatingPeriodArchive.period_month == month)
    )
    total = count_result.scalar()

    return {
        "period_year": year,
        "period_month": month,
        "archives": [
            {
                "user_id": a.user_id,
                "final_krk": a.final_krk,
                "final_rank": a.final_rank,
                "league": a.league
            }
            for a in archives
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }