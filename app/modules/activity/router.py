from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.modules.activity.logic import (
    get_personalized_feed_logic,
    get_team_activity_feed_logic
)
from app.modules.activity.schemas import ActivityFeedResponse

router = APIRouter(prefix="/feed", tags=["Activity Feed"])


@router.get("", response_model=ActivityFeedResponse)
async def get_personalized_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Персонализированная лента активностей для текущего пользователя"""
    return await get_personalized_feed_logic(current_user.id, limit, offset, db)


@router.get("/team/{team_id}", response_model=ActivityFeedResponse)
async def get_team_feed(
    team_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Лента активностей конкретной команды"""
    return await get_team_activity_feed_logic(team_id, limit, offset, db)
