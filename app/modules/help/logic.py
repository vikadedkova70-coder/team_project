from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from datetime import datetime
from app.models.reports import HelpRequest, HelpResponse
from app.models.team import Team
from app.models.activity import Activity
from app.models.rating import TeamRatingLog


HELP_BONUS = 0.5
MAX_RATING = 5.0


async def create_help_request_logic(
    team_id: int,
    user_id: int,
    title: str,
    description: str | None,
    help_type: str,
    format: str,
    estimated_effort_hours: int | None,
    db: AsyncSession
) -> HelpRequest:
    """Создание заявки на помощь"""
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Команда не найдена")

    request = HelpRequest(
        requesting_team_id=team_id,
        title=title,
        description=description,
        help_type=help_type,
        format=format,
        estimated_effort_hours=estimated_effort_hours,
        status="open"
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


async def respond_to_help_logic(
    request_id: int,
    team_id: int,
    message: str | None,
    db: AsyncSession
) -> HelpResponse:
    """Отклик на заявку помощи"""
    request = await db.get(HelpRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if request.status != "open":
        raise HTTPException(status_code=400, detail="Заявка уже закрыта")
    if request.requesting_team_id == team_id:
        raise HTTPException(status_code=400, detail="Нельзя откликнуться на свою заявку")

    existing = await db.execute(
        select(HelpResponse).where(
            HelpResponse.help_request_id == request_id,
            HelpResponse.responding_team_id == team_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Вы уже откликнулись")

    response = HelpResponse(
        help_request_id=request_id,
        responding_team_id=team_id,
        message=message,
        status="pending"
    )
    db.add(response)
    await db.commit()
    await db.refresh(response)
    return response


async def accept_help_logic(
    request_id: int,
    response_id: int,
    db: AsyncSession
) -> HelpRequest:
    """Принятие помощи — начисление баллов обеим командам"""
    request = await db.get(HelpRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if request.status != "open":
        raise HTTPException(status_code=400, detail="Заявка уже закрыта")

    response = await db.get(HelpResponse, response_id)
    if not response or response.help_request_id != request_id:
        raise HTTPException(status_code=404, detail="Отклик не найден")

    requesting_team = await db.get(Team, request.requesting_team_id)
    responding_team = await db.get(Team, response.responding_team_id)

    old_req_rating = requesting_team.rating
    old_res_rating = responding_team.rating

    requesting_team.rating = min(MAX_RATING, requesting_team.rating + HELP_BONUS)
    responding_team.rating = min(MAX_RATING, responding_team.rating + HELP_BONUS)

    request.status = "fulfilled"
    request.fulfilled_by_team_id = responding_team.id
    request.fulfilled_at = datetime.utcnow()

    response.status = "accepted"

    for team, old_rating, new_rating in [
        (requesting_team, old_req_rating, requesting_team.rating),
        (responding_team, old_res_rating, responding_team.rating)
    ]:
        rating_log = TeamRatingLog(
            team_id=team.id,
            event_type="help_fulfilled",
            old_rating=old_rating,
            new_rating=new_rating,
            description=f"Помощь команде: {request.title}"
        )
        db.add(rating_log)

        activity = Activity(
            team_id=team.id,
            event_type="achievement",
            title="Помощь оказана",
            description=f"Команда помогла другой команде, рейтинг: {old_rating:.2f} → {new_rating:.2f}",
            metadata={"help_request_id": request_id}
        )
        db.add(activity)

    await db.commit()
    await db.refresh(request)
    return request


async def cancel_help_request_logic(
    request_id: int,
    db: AsyncSession
) -> HelpRequest:
    """Отмена заявки"""
    request = await db.get(HelpRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if request.status != "open":
        raise HTTPException(status_code=400, detail="Заявка уже закрыта")

    request.status = "cancelled"
    await db.commit()
    await db.refresh(request)
    return request


async def get_help_requests_logic(
    status: str | None = None,
    help_type: str | None = None,
    db: AsyncSession = None
) -> tuple[list[HelpRequest], int]:
    """Список заявок"""
    query = select(HelpRequest)
    if status:
        query = query.where(HelpRequest.status == status)
    if help_type:
        query = query.where(HelpRequest.help_type == help_type)

    result = await db.execute(
        query.where(HelpRequest.status != "fulfilled").order_by(HelpRequest.created_at.desc())
    )
    requests = result.scalars().all()

    count_result = await db.execute(select(HelpRequest))
    total = len(count_result.scalars().all())

    return requests, total


async def get_help_request_detail_logic(
    request_id: int,
    db: AsyncSession
) -> HelpRequest:
    """Детали заявки"""
    request = await db.get(HelpRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return request