from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_captain
from app.models.user import User
from app.models.team import TeamMember
from app.modules.events.logic import (
    create_event_logic,
    get_events_logic,
    get_event_detail_logic,
    invite_team_logic,
    respond_invitation_logic,
    rsvp_event_logic,
    delete_event_logic
)
from app.modules.events.schemas import (
    EventCreateRequest,
    EventResponse,
    EventDetailResponse,
    InvitationRespondRequest
)
from sqlalchemy import select

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("")
async def list_events(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Публичный список событий"""
    events, total = await get_events_logic(limit, offset, db)
    return {
        "events": [
            EventResponse(
                id=e.id,
                team_id=e.team_id,
                title=e.title,
                description=e.description,
                event_type=e.event_type,
                format=e.format,
                location=e.location,
                starts_at=e.starts_at,
                ends_at=e.ends_at,
                max_participants=e.max_participants,
                is_public=e.is_public,
                created_by=e.created_by,
                created_at=e.created_at
            )
            for e in events
        ],
        "total": total
    }


@router.post("")
async def create_event(
    data: EventCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Создать событие"""
    membership_result = await db.execute(
        select(TeamMember).where(TeamMember.user_id == current_user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не состоите в команде")

    event = await create_event_logic(membership.team_id, current_user.id, data, db)
    return EventResponse(
        id=event.id,
        team_id=event.team_id,
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        format=event.format,
        location=event.location,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        max_participants=event.max_participants,
        is_public=event.is_public,
        created_by=event.created_by,
        created_at=event.created_at
    )


@router.get("/{event_id}")
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Детали события"""
    event = await get_event_detail_logic(event_id, db)
    return EventDetailResponse(
        id=event.id,
        team_id=event.team_id,
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        format=event.format,
        location=event.location,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        max_participants=event.max_participants,
        is_public=event.is_public,
        created_by=event.created_by,
        created_at=event.created_at,
        invitations=[],
        participants=[]
    )


@router.post("/{event_id}/invite/{team_id}")
async def invite_to_event(
    event_id: int,
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Пригласить команду на событие"""
    membership_result = await db.execute(
        select(TeamMember).where(TeamMember.user_id == current_user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не состоите в команде")

    invitation = await invite_team_logic(event_id, team_id, db)
    return {"message": "Команда приглашена", "invitation_id": invitation.id}


@router.post("/{event_id}/rsvp")
async def rsvp_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Зарегистрироваться на событие"""
    participant = await rsvp_event_logic(event_id, current_user.id, db)
    return {"message": "Вы зарегистрированы", "participant_id": participant.id}


@router.post("/invitations/{invitation_id}/respond")
async def respond_invitation(
    invitation_id: int,
    data: InvitationRespondRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Ответить на приглашение"""
    membership_result = await db.execute(
        select(TeamMember).where(TeamMember.user_id == current_user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не состоите в команде")

    invitation = await respond_invitation_logic(invitation_id, membership.team_id, data.accept, db)
    return {"message": "Ответ отправлен", "status": invitation.status}


@router.delete("/{event_id}")
async def remove_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Удалить событие (создатель)"""
    await delete_event_logic(event_id, current_user.id, db)
    return {"message": "Событие удалено"}
