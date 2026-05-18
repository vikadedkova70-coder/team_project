from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from app.models.team import Team, TeamMember
from app.models.activity import Activity
from app.models.rating import TeamRatingLog
from app.models.user import User
from app.modules.team_profile.schemas import (
    TeamProfileResponse,
    RatingLogResponse,
    ActivityResponse
)


async def get_team_profile_logic(team_id: int, db: AsyncSession) -> TeamProfileResponse:
    """Получение профиля команды"""
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Команда не найдена")

    captain = await db.get(User, team.captain_id)
    captain_name = None
    if captain and captain.student:
        captain_name = f"{captain.student.surname} {captain.student.name}"

    # Rating history
    logs_result = await db.execute(
        select(TeamRatingLog)
        .where(TeamRatingLog.team_id == team_id)
        .order_by(TeamRatingLog.created_at.desc())
        .limit(20)
    )
    rating_logs = logs_result.scalars().all()

    # Recent activities
    acts_result = await db.execute(
        select(Activity)
        .where(Activity.team_id == team_id)
        .order_by(Activity.created_at.desc())
        .limit(10)
        .options(selectinload(Activity.user))
    )
    activities = acts_result.scalars().all()

    # Members count
    members_result = await db.execute(
        select(TeamMember).where(TeamMember.team_id == team_id)
    )
    members_count = len((members_result.scalars().all()))

    return TeamProfileResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        captain_id=team.captain_id,
        captain_name=captain_name,
        members_count=members_count,
        rating=team.rating,
        rating_history=[
            RatingLogResponse(
                id=log.id,
                event_type=log.event_type,
                old_rating=log.old_rating,
                new_rating=log.new_rating,
                description=log.description,
                created_at=log.created_at
            )
            for log in rating_logs
        ],
        recent_activities=[
            ActivityResponse(
                id=act.id,
                team_id=act.team_id,
                user_id=act.user_id,
                event_type=act.event_type,
                title=act.title,
                description=act.description,
                metadata=act.metadata,
                created_at=act.created_at
            )
            for act in activities
        ],
        created_at=team.created_at
    )