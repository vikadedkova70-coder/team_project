from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from datetime import datetime
from app.models.reports import WeeklyCheckin, CheckinTask
from app.models.team import Team, TeamMember
from app.models.user import User


async def create_checkin_logic(
    team_id: int,
    user_id: int,
    week_start_date,
    content: str | None,
    db: AsyncSession
) -> WeeklyCheckin:
    """Создание check-in"""
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Команда не найдена")

    checkin = WeeklyCheckin(
        team_id=team_id,
        week_start_date=week_start_date,
        content=content,
        created_by=user_id,
        status="pending"
    )
    db.add(checkin)
    await db.commit()
    await db.refresh(checkin)
    return checkin


async def add_task_to_checkin_logic(
    checkin_id: int,
    user_id: int,
    description: str,
    db: AsyncSession
) -> CheckinTask:
    """Добавление задачи в check-in"""
    task = CheckinTask(
        checkin_id=checkin_id,
        user_id=user_id,
        description=description,
        completed=False
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def complete_checkin_task_logic(
    task_id: int,
    user_id: int,
    db: AsyncSession
) -> CheckinTask:
    """Выполнение задачи в check-in"""
    task = await db.get(CheckinTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if task.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нет прав")

    task.completed = True
    task.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return task


async def get_team_checkins_logic(
    team_id: int,
    db: AsyncSession
) -> list[WeeklyCheckin]:
    """Получение check-ins команды"""
    result = await db.execute(
        select(WeeklyCheckin)
        .where(WeeklyCheckin.team_id == team_id)
        .order_by(WeeklyCheckin.created_at.desc())
    )
    return result.scalars().all()


async def get_pending_checkins_logic(
    db: AsyncSession
) -> list[WeeklyCheckin]:
    """Ожидающие проверки check-ins (для преподавателей)"""
    result = await db.execute(
        select(WeeklyCheckin)
        .where(WeeklyCheckin.status == "pending")
        .order_by(WeeklyCheckin.created_at.asc())
    )
    return result.scalars().all()


async def review_checkin_logic(
    checkin_id: int,
    reviewer_id: int,
    db: AsyncSession
) -> WeeklyCheckin:
    """Проверка check-in преподавателем"""
    checkin = await db.get(WeeklyCheckin, checkin_id)
    if not checkin:
        raise HTTPException(status_code=404, detail="Check-in не найден")

    checkin.reviewed_by = reviewer_id
    checkin.reviewed_at = datetime.utcnow()
    checkin.status = "reviewed"
    await db.commit()
    await db.refresh(checkin)
    return checkin
