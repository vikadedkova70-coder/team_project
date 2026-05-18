from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_captain
from app.modules.team.logic import (
    get_user_profile_logic,
    create_team_logic,
    search_teams_logic,
    create_invite_link_logic,
    join_by_link_logic,
    create_join_request_logic,
    get_team_requests_logic,
    process_join_request_logic,
    get_team_detail_logic,
    update_team_logic,
    leave_team_logic,
    disband_team_logic,
    get_my_invite_links_logic,
    revoke_invite_link_logic
)
from app.modules.team.schemas import (
    UserProfileResponse,
    TeamCreateRequest,
    TeamResponse,
    InviteLinkCreateRequest,
    InviteLinkResponse,
    JoinByLinkRequest,
    JoinRequestResponse,
    JoinRequestAction,
    TeamUpdateRequest,
    TeamDetailResponse,
    TeamMemberResponse,
    InviteLinkListResponse
)
from app.models.user import User, Student
from app.models.team import Team

router = APIRouter(prefix="/team", tags=["Team"])


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получение данных личного кабинета"""
    return await get_user_profile_logic(current_user, db)


@router.post("/create", response_model=TeamResponse)
async def create_team(
    data: TeamCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Создание новой команды"""
    team = await create_team_logic(current_user, data, db)

    captain_name = None
    student_id = current_user.student_id
    if student_id:
        from app.models.user import Student
        student = await db.get(Student, student_id)
        if student:
            captain_name = f"{student.surname} {student.name}"

    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        captain_id=team.captain_id,
        captain_name=captain_name,
        members_count=1,
        created_at=team.created_at
    )


@router.get("/search")
async def search_teams(
    query: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db)
):
    """Поиск команд по названию"""
    teams = await search_teams_logic(query, db)

    result = []
    for team in teams:
        captain_name = None
        if team.captain_id:
            captain_result = await db.execute(
                select(User)
                .where(User.id == team.captain_id)
                .options(selectinload(User.student))
            )
            captain = captain_result.scalar_one_or_none()
            if captain and captain.student:
                captain_name = f"{captain.student.surname} {captain.student.name}"

        result.append({
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "captain_id": team.captain_id,
            "captain_name": captain_name,
            "members_count": len(team.members),
            "created_at": team.created_at
        })

    return result


@router.post("/{team_id}/invite", response_model=InviteLinkResponse)
async def create_invite_link(
    team_id: int,
    data: InviteLinkCreateRequest,
    current_user: User = Depends(get_current_captain),
    db: AsyncSession = Depends(get_db)
):
    """Создание пригласительной ссылки"""
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()

    if not team or team.captain_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав для этой команды")

    link = await create_invite_link_logic(
        team=team,
        expires_hours=data.expires_hours,
        max_uses=data.max_uses,
        db=db
    )

    return InviteLinkResponse(
        token=link.token,
        team_name=team.name,
        expires_at=link.expires_at,
        max_uses=link.max_uses,
        uses_count=link.uses_count,
        is_active=link.is_active
    )


@router.post("/join-by-link")
async def join_by_link(
    data: JoinByLinkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Вступление в команду по пригласительной ссылке"""
    team = await join_by_link_logic(data.token, current_user, db)
    return {"message": "Вы успешно присоединились к команде", "team_name": team.name}


@router.post("/{team_id}/join-request")
async def send_join_request(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Отправка заявки на вступление в команду"""
    request = await create_join_request_logic(team_id, current_user, db)
    return {"message": "Заявка отправлена", "request_id": request.id}


@router.get("/{team_id}/requests")
async def get_join_requests(
    team_id: int,
    current_user: User = Depends(get_current_captain),
    db: AsyncSession = Depends(get_db)
):
    """Получение всех заявок для команды"""
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()

    if not team or team.captain_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав для этой команды")

    requests = await get_team_requests_logic(team, db)

    result = []
    for req in requests:
        user_result = await db.execute(select(User).where(User.id == req.user_id))
        user = user_result.scalar_one()

        full_name = "Unknown"
        if user.student_id:
            student = await db.get(Student, user.student_id)
            if student:
                full_name = f"{student.surname} {student.name} {student.patronymic}"

        result.append({
            "id": req.id,
            "user_id": req.user_id,
            "username": user.username,
            "full_name": full_name,
            "status": req.status,
            "created_at": req.created_at
        })

    return result


@router.post("/requests/{request_id}/process")
async def process_request(
    request_id: int,
    data: JoinRequestAction,
    current_user: User = Depends(get_current_captain),
    db: AsyncSession = Depends(get_db)
):
    """Обработка заявки на вступление"""
    request = await process_join_request_logic(request_id, data.action, current_user, db)
    return {"message": f"Заявка {data.action}ена", "request_id": request.id}


@router.get("/{team_id}", response_model=TeamDetailResponse)
async def get_team_detail(
    team_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Просмотр информации о команде"""
    return await get_team_detail_logic(team_id, db)


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: int,
    data: TeamUpdateRequest,
    current_user: User = Depends(get_current_captain),
    db: AsyncSession = Depends(get_db)
):
    """Обновление команды (капитан)"""
    team = await update_team_logic(team_id, current_user, data, db)
    result = await get_team_detail_logic(team_id, db)
    return TeamResponse(
        id=result["id"],
        name=result["name"],
        description=result["description"],
        captain_id=result["captain_id"],
        captain_name=result["captain_name"],
        members_count=result["members_count"],
        created_at=result["created_at"]
    )


@router.delete("/leave")
async def leave_team(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Выход из команды (студент)"""
    await leave_team_logic(current_user, db)
    return {"message": "Вы покинули команду"}


@router.delete("/{team_id}")
async def disband_team(
    team_id: int,
    current_user: User = Depends(get_current_captain),
    db: AsyncSession = Depends(get_db)
):
    """Роспуск команды (капитан)"""
    await disband_team_logic(team_id, current_user, db)
    return {"message": "Команда распущена"}


@router.get("/{team_id}/invites", response_model=InviteLinkListResponse)
async def get_my_invite_links(
    team_id: int,
    current_user: User = Depends(get_current_captain),
    db: AsyncSession = Depends(get_db)
):
    """Получение списка активных пригласительных ссылок"""
    links = await get_my_invite_links_logic(team_id, current_user, db)
    return InviteLinkListResponse(
        links=[
            InviteLinkResponse(
                token=link.token,
                team_name=(await db.get(Team, link.team_id)).name,
                expires_at=link.expires_at,
                max_uses=link.max_uses,
                uses_count=link.uses_count,
                is_active=link.is_active
            )
            for link in links
        ]
    )


@router.delete("/invite/{link_id}")
async def revoke_invite_link(
    link_id: int,
    current_user: User = Depends(get_current_captain),
    db: AsyncSession = Depends(get_db)
):
    """Отзыв пригласительной ссылки"""
    link = await revoke_invite_link_logic(link_id, current_user, db)
    return {"message": "Ссылка отозвана", "link_id": link.id}
