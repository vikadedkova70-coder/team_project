from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.models.user import User, UserRole, Student
from app.models.team import Team, TeamMember, TeamInviteLink, TeamJoinRequest
from app.modules.team.schemas import TeamCreateRequest
from datetime import datetime, timedelta
import secrets


async def get_user_profile_logic(user: User, db: AsyncSession) -> dict:
    """Получение данных профиля пользователя"""
    student = None
    if user.student_id:
        student = await db.get(Student, user.student_id)

    if student:
        full_name = f"{student.surname} {student.name} {student.patronymic}"
    else:
        full_name = "Unknown"

    team_name = None
    team_id = None

    if user.id:
        membership = await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id)
        )
        membership = membership.scalar_one_or_none()
        if membership and membership.team_id:
            team = await db.get(Team, membership.team_id)
            if team:
                team_name = team.name
                team_id = team.id

    return {
        "username": user.username,
        "student_id": user.student_id,
        "full_name": full_name,
        "role": user.role,
        "team_name": team_name,
        "team_id": team_id
    }


async def create_team_logic(user: User, data: TeamCreateRequest, db: AsyncSession) -> Team:
    """Создание новой команды"""
    membership = await db.execute(
        select(TeamMember).where(TeamMember.user_id == user.id)
    )
    if membership.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Вы уже состоите в команде")

    existing = await db.execute(select(Team).where(Team.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Команда с таким названием уже существует")

    team = Team(
        name=data.name,
        description=data.description,
        captain_id=user.id
    )
    db.add(team)
    await db.flush()

    membership = TeamMember(user_id=user.id, team_id=team.id)
    db.add(membership)

    user.role = UserRole.CAPTAIN.value

    await db.commit()
    await db.refresh(team)

    return team


async def search_teams_logic(query: str, db: AsyncSession) -> list:
    """Поиск команд по названию"""
    result = await db.execute(
        select(Team)
        .where(Team.name.ilike(f"%{query}%"))
        .options(selectinload(Team.members))
    )
    return result.scalars().all()


async def create_invite_link_logic(team: Team, expires_hours: int = 24,
                                   max_uses: int = None, db: AsyncSession = None) -> TeamInviteLink:
    """Создание пригласительной ссылки"""
    token = secrets.token_urlsafe(32)

    expires_at = None
    if expires_hours:
        # 🔧 Используем naive datetime для совместимости с БД
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)

    link = TeamInviteLink(
        team_id=team.id,
        token=token,
        expires_at=expires_at,
        max_uses=max_uses,
        uses_count=0,
        is_active=True
    )

    db.add(link)
    await db.commit()
    await db.refresh(link)

    return link


async def join_by_link_logic(token: str, user: User, db: AsyncSession) -> Team:
    """Вступление в команду по пригласительной ссылке"""
    link_result = await db.execute(select(TeamInviteLink).where(TeamInviteLink.token == token))
    link = link_result.scalar_one_or_none()

    if not link or not link.is_active:
        raise HTTPException(status_code=400, detail="Недействительная ссылка")

    # 🔧 Используем naive datetime для сравнения
    if link.expires_at and datetime.utcnow() > link.expires_at:
        raise HTTPException(status_code=400, detail="Срок действия ссылки истёк")

    if link.max_uses and link.uses_count >= link.max_uses:
        raise HTTPException(status_code=400, detail="Лимит использований ссылки исчерпан")

    membership = await db.execute(
        select(TeamMember).where(TeamMember.user_id == user.id)
    )
    if membership.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Вы уже состоите в команде")

    team = await db.get(Team, link.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Команда не найдена")

    new_membership = TeamMember(user_id=user.id, team_id=team.id)
    db.add(new_membership)

    link.uses_count += 1
    if link.max_uses and link.uses_count >= link.max_uses:
        link.is_active = False

    await db.commit()

    return team


async def create_join_request_logic(team_id: int, user: User, db: AsyncSession) -> TeamJoinRequest:
    """Создание заявки на вступление в команду"""
    membership = await db.execute(
        select(TeamMember).where(TeamMember.user_id == user.id)
    )
    if membership.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Вы уже состоите в команде")

    existing = await db.execute(
        select(TeamJoinRequest).where(
            TeamJoinRequest.user_id == user.id,
            TeamJoinRequest.team_id == team_id,
            TeamJoinRequest.status == "pending"
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Заявка уже отправлена")

    request = TeamJoinRequest(user_id=user.id, team_id=team_id, status="pending")
    db.add(request)
    await db.commit()
    await db.refresh(request)

    return request


async def get_team_requests_logic(team: Team, db: AsyncSession) -> list:
    """Получение всех заявок для команды"""
    result = await db.execute(
        select(TeamJoinRequest)
        .where(TeamJoinRequest.team_id == team.id)
        .where(TeamJoinRequest.status == "pending")
    )
    return result.scalars().all()


async def process_join_request_logic(request_id: int, action: str, captain: User,
                                     db: AsyncSession) -> TeamJoinRequest:
    """Обработка заявки на вступление"""
    request_result = await db.execute(select(TeamJoinRequest).where(TeamJoinRequest.id == request_id))
    request = request_result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    team = await db.get(Team, request.team_id)
    if not team or team.captain_id != captain.id:
        raise HTTPException(status_code=403, detail="Нет прав для этой команды")

    if action == "approve":
        member_check = await db.execute(
            select(TeamMember).where(TeamMember.user_id == request.user_id)
        )
        if member_check.scalar_one_or_none():
            request.status = "rejected"
            await db.commit()
            raise HTTPException(status_code=400, detail="Пользователь уже в команде")

        membership = TeamMember(user_id=request.user_id, team_id=team.id)
        db.add(membership)
        request.status = "approved"

    elif action == "reject":
        request.status = "rejected"
    else:
        raise HTTPException(status_code=400, detail="Неверное действие")

    await db.commit()
    await db.refresh(request)

    return request