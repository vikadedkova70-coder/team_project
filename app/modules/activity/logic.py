from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from app.models.activity import Activity
from app.models.rating import TeamRatingLog
from app.models.team import Team, TeamMember
from app.models.user import User
from app.modules.activity.schemas import ActivityResponse, ActivityFeedResponse
from datetime import datetime
from typing import Optional


async def create_activity_logic(
    team_id: int,
    event_type: str,
    title: str,
    user_id: Optional[int] = None,
    description: Optional[str] = None,
    metadata: Optional[dict] = None,
    db: AsyncSession = None
) -> Activity:
    """Создание записи активности"""
    activity = Activity(
        team_id=team_id,
        user_id=user_id,
        event_type=event_type,
        title=title,
        description=description,
        metadata=metadata
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


async def get_personalized_feed_logic(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = None
) -> ActivityFeedResponse:
    """Персонализированная лента для пользователя"""
    # Find user's team
    membership_result = await db.execute(
        select(TeamMember).where(TeamMember.user_id == user_id)
    )
    membership = membership_result.scalar_one_or_none()

    if not membership:
        return ActivityFeedResponse(activities=[], total=0)

    result = await db.execute(
        select(Activity)
        .where(Activity.team_id == membership.team_id)
        .order_by(Activity.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(selectinload(Activity.user))
    )
    activities = result.scalars().all()

    count_result = await db.execute(
        select(Activity).where(Activity.team_id == membership.team_id)
    )
    total = len(count_result.scalars().all())

    return ActivityFeedResponse(
        activities=[
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
        total=total
    )


async def get_team_activity_feed_logic(
    team_id: int,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = None
) -> ActivityFeedResponse:
    """Лента активностей конкретной команды"""
    result = await db.execute(
        select(Activity)
        .where(Activity.team_id == team_id)
        .order_by(Activity.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(selectinload(Activity.user))
    )
    activities = result.scalars().all()

    count_result = await db.execute(
        select(Activity).where(Activity.team_id == team_id)
    )
    total = len(count_result.scalars().all())

    return ActivityFeedResponse(
        activities=[
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
        total=total
    )