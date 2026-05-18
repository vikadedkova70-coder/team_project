from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from datetime import datetime
from app.models.reports import TeamReport, ReportFile, ReportTask
from app.models.team import Team


async def create_report_logic(
    team_id: int,
    user_id: int,
    title: str,
    description: str | None,
    challenge_id: int | None,
    db: AsyncSession
) -> TeamReport:
    """Создание отчёта"""
    report = TeamReport(
        team_id=team_id,
        title=title,
        description=description,
        challenge_id=challenge_id,
        created_by=user_id,
        is_approved=False
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def add_report_file_logic(
    report_id: int,
    filename: str,
    file_path: str,
    file_size: int,
    content_type: str,
    db: AsyncSession
) -> ReportFile:
    """Добавление файла к отчёту"""
    file = ReportFile(
        report_id=report_id,
        filename=filename,
        file_path=file_path,
        file_size=file_size,
        content_type=content_type
    )
    db.add(file)
    await db.commit()
    await db.refresh(file)
    return file


async def assign_task_logic(
    report_id: int,
    user_id: int,
    description: str,
    db: AsyncSession
) -> ReportTask:
    """Назначение задачи в отчёте"""
    task = ReportTask(
        report_id=report_id,
        user_id=user_id,
        description=description,
        completed=False
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def complete_task_logic(
    task_id: int,
    user_id: int,
    db: AsyncSession
) -> ReportTask:
    """Выполнение задачи"""
    task = await db.get(ReportTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if task.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нет прав")

    task.completed = True
    task.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return task


async def get_team_reports_logic(
    team_id: int,
    db: AsyncSession
) -> list[TeamReport]:
    """Список отчётов команды"""
    result = await db.execute(
        select(TeamReport)
        .where(TeamReport.team_id == team_id)
        .order_by(TeamReport.created_at.desc())
    )
    return result.scalars().all()
