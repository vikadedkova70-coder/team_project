from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin_or_teacher
from app.models.user import User
from app.models.team import TeamMember
from sqlalchemy import select
from app.modules.checkin.logic import (
    create_checkin_logic,
    add_task_to_checkin_logic,
    complete_checkin_task_logic,
    get_team_checkins_logic,
    get_pending_checkins_logic,
    review_checkin_logic
)
from app.modules.checkin.schemas import (
    CheckinCreateRequest,
    CheckinResponse,
    CheckinTaskRequest
)

router = APIRouter(prefix="/checkins", tags=["Check-in"])


@router.post("")
async def create_checkin(
    data: CheckinCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Создать еженедельный check-in"""
    membership_result = await db.execute(
        select(TeamMember).where(TeamMember.user_id == current_user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не состоите в команде")

    checkin = await create_checkin_logic(
        membership.team_id, current_user.id, data.week_start_date, data.content, db
    )
    return CheckinResponse(
        id=checkin.id,
        team_id=checkin.team_id,
        week_start_date=checkin.week_start_date,
        content=checkin.content,
        created_by=checkin.created_by,
        created_at=checkin.created_at,
        reviewed_by=checkin.reviewed_by,
        reviewed_at=checkin.reviewed_at,
        status=checkin.status,
        tasks=[]
    )


@router.get("/team/{team_id}")
async def get_team_checkins(
    team_id: int,
    db: AsyncSession = Depends(get_db)
):
    """История check-ins команды"""
    checkins = await get_team_checkins_logic(team_id, db)
    return {
        "checkins": [
            CheckinResponse(
                id=c.id,
                team_id=c.team_id,
                week_start_date=c.week_start_date,
                content=c.content,
                created_by=c.created_by,
                created_at=c.created_at,
                reviewed_by=c.reviewed_by,
                reviewed_at=c.reviewed_at,
                status=c.status,
                tasks=[]
            )
            for c in checkins
        ],
        "total": len(checkins)
    }


@router.get("/pending")
async def get_pending_checkins(
    current_user: User = Depends(get_current_admin_or_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Ожидающие проверки (преподаватель/админ)"""
    checkins = await get_pending_checkins_logic(db)
    return {
        "checkins": [
            CheckinResponse(
                id=c.id,
                team_id=c.team_id,
                week_start_date=c.week_start_date,
                content=c.content,
                created_by=c.created_by,
                created_at=c.created_at,
                reviewed_by=c.reviewed_by,
                reviewed_at=c.reviewed_at,
                status=c.status,
                tasks=[]
            )
            for c in checkins
        ],
        "total": len(checkins)
    }


@router.post("/{checkin_id}/review")
async def review_checkin(
    checkin_id: int,
    current_user: User = Depends(get_current_admin_or_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Проверить check-in (преподаватель/админ)"""
    checkin = await review_checkin_logic(checkin_id, current_user.id, db)
    return {"message": "Check-in проверен", "checkin_id": checkin.id}


@router.post("/{checkin_id}/tasks")
async def add_checkin_task(
    checkin_id: int,
    data: CheckinTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Добавить задачу в check-in"""
    task = await add_task_to_checkin_logic(checkin_id, data.user_id, data.description, db)
    return {"message": "Задача добавлена", "task_id": task.id}


from fastapi import HTTPException
