from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin_or_teacher
from app.models.user import User
from app.models.team import TeamMember
from app.modules.help.logic import (
    create_help_request_logic,
    respond_to_help_logic,
    accept_help_logic,
    cancel_help_request_logic,
    get_help_requests_logic,
    get_help_request_detail_logic
)
from app.modules.help.schemas import (
    HelpRequestCreate,
    HelpResponseCreate,
    HelpRequestResponse,
    HelpRequestDetailResponse
)
from sqlalchemy import select

router = APIRouter(prefix="/help", tags=["Help"])


@router.get("")
async def list_help_requests(
    status: str = Query(None),
    help_type: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Список заявок на помощь"""
    requests, total = await get_help_requests_logic(status, help_type, db)
    return {
        "requests": [
            HelpRequestResponse(
                id=r.id,
                requesting_team_id=r.requesting_team_id,
                title=r.title,
                description=r.description,
                help_type=r.help_type,
                format=r.format,
                estimated_effort_hours=r.estimated_effort_hours,
                status=r.status,
                created_at=r.created_at,
                fulfilled_by_team_id=r.fulfilled_by_team_id,
                fulfilled_at=r.fulfilled_at
            )
            for r in requests
        ],
        "total": total
    }


@router.post("")
async def create_help_request(
    data: HelpRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Создать заявку на помощь"""
    membership_result = await db.execute(
        select(TeamMember).where(TeamMember.user_id == current_user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не состоите в команде")

    request = await create_help_request_logic(
        membership.team_id, current_user.id,
        data.title, data.description, data.help_type,
        data.format, data.estimated_effort_hours, db
    )
    return HelpRequestResponse(
        id=request.id,
        requesting_team_id=request.requesting_team_id,
        title=request.title,
        description=request.description,
        help_type=request.help_type,
        format=request.format,
        estimated_effort_hours=request.estimated_effort_hours,
        status=request.status,
        created_at=request.created_at,
        fulfilled_by_team_id=request.fulfilled_by_team_id,
        fulfilled_at=request.fulfilled_at
    )


@router.get("/{request_id}")
async def get_help_request(
    request_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Детали заявки"""
    request = await get_help_request_detail_logic(request_id, db)
    return HelpRequestDetailResponse(
        id=request.id,
        requesting_team_id=request.requesting_team_id,
        title=request.title,
        description=request.description,
        help_type=request.help_type,
        format=request.format,
        estimated_effort_hours=request.estimated_effort_hours,
        status=request.status,
        created_at=request.created_at,
        fulfilled_by_team_id=request.fulfilled_by_team_id,
        fulfilled_at=request.fulfilled_at,
        responses=[]
    )


@router.post("/{request_id}/respond")
async def respond_to_help(
    request_id: int,
    data: HelpResponseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Откликнуться на заявку"""
    membership_result = await db.execute(
        select(TeamMember).where(TeamMember.user_id == current_user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не состоите в команде")

    response = await respond_to_help_logic(request_id, membership.team_id, data.message, db)
    return {"message": "Отклик отправлен", "response_id": response.id}


@router.post("/{request_id}/accept/{response_id}")
async def accept_help(
    request_id: int,
    response_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Принять помощь — начислить баллы"""
    request = await accept_help_logic(request_id, response_id, db)
    return {"message": "Помощь принята, +0.5 к рейтингу обеих команд"}


@router.post("/{request_id}/cancel")
async def cancel_help_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Отменить заявку"""
    request = await cancel_help_request_logic(request_id, db)
    return {"message": "Заявка отменена"}
