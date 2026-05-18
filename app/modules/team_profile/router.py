from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.modules.team_profile.logic import get_team_profile_logic
from app.modules.team_profile.schemas import TeamProfileResponse

router = APIRouter(prefix="/teams", tags=["Team Profile"])


@router.get("/{team_id}/profile", response_model=TeamProfileResponse)
async def get_team_profile(
    team_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Профиль команды с составом участников, рейтингом и историей активности"""
    return await get_team_profile_logic(team_id, db)
