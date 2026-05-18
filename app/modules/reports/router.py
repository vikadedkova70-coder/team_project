from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.team import TeamMember
from app.modules.reports.logic import (
    create_report_logic,
    add_report_file_logic,
    assign_task_logic,
    complete_task_logic,
    get_team_reports_logic,
)
from app.modules.reports.schemas import (
    ReportCreateRequest,
    ReportResponse,
    ReportFileResponse,
    ReportTaskAssignRequest,
    ReportTaskResponse,
)
from sqlalchemy import select
from pathlib import Path
import uuid
import shutil

router = APIRouter(prefix="/reports", tags=["Reports"])

REPORT_UPLOAD_DIR = Path("uploads/reports")


async def ensure_report_upload_dir():
    """Создаёт директорию для загрузок отчётов"""
    REPORT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_report_file(file: UploadFile, report_id: int) -> tuple[str, str, int]:
    """Сохраняет файл отчёта"""
    file_extension = Path(file.filename).suffix.lower() if file.filename else ""
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    file_path = REPORT_UPLOAD_DIR / unique_filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = file_path.stat().st_size
    return file.filename or "unknown", str(file_path), file_size


def build_report_response(report) -> ReportResponse:
    """Строит ответ отчёта"""
    return ReportResponse(
        id=report.id,
        team_id=report.team_id,
        challenge_id=report.challenge_id,
        title=report.title,
        description=report.description,
        created_by=report.created_by,
        created_at=report.created_at,
        is_approved=report.is_approved,
        files=[
            ReportFileResponse(
                id=f.id,
                filename=f.filename,
                file_size=f.file_size,
                content_type=f.content_type,
                uploaded_at=f.uploaded_at or report.created_at,
            )
            for f in report.files
        ],
        tasks=[
            ReportTaskResponse(
                id=t.id,
                user_id=t.user_id,
                description=t.description,
                completed=t.completed,
                completed_at=t.completed_at,
            )
            for t in report.tasks
        ],
    )


@router.post("")
async def create_report(
    title: str = Form(..., min_length=3, max_length=200),
    description: str = Form(None),
    challenge_id: int = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создать отчёт команды"""
    membership_result = await db.execute(
        select(TeamMember).where(TeamMember.user_id == current_user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=400, detail="Вы не состоите в команде")

    report = await create_report_logic(
        membership.team_id, current_user.id,
        title, description, challenge_id, db
    )
    return build_report_response(report)


@router.post("/{report_id}/files")
async def upload_report_file(
    report_id: int,
    files: List[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Загрузить файлы к отчёту"""
    await ensure_report_upload_dir()

    added = []
    for file in files:
        if not file.filename:
            continue

        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"Файл {file.filename} слишком большой (максимум 10MB)"
            )

        filename, file_path, size = save_report_file(file, report_id)
        report_file = await add_report_file_logic(
            report_id, filename, file_path, size,
            file.content_type or "application/octet-stream", db
        )
        added.append(ReportFileResponse(
            id=report_file.id,
            filename=report_file.filename,
            file_size=report_file.file_size,
            content_type=report_file.content_type,
            uploaded_at=report_file.uploaded_at
        ))

    return {"files": added}


@router.get("/team/{team_id}")
async def get_team_reports(
    team_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Список отчётов команды"""
    reports = await get_team_reports_logic(team_id, db)
    return {"reports": [build_report_response(r) for r in reports], "total": len(reports)}


@router.post("/{report_id}/tasks")
async def assign_report_task(
    report_id: int,
    data: ReportTaskAssignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Назначить задачу в отчёте"""
    task = await assign_task_logic(report_id, data.user_id, data.description, db)
    return ReportTaskResponse(
        id=task.id,
        user_id=task.user_id,
        description=task.description,
        completed=task.completed,
        completed_at=task.completed_at
    )


@router.post("/tasks/{task_id}/complete")
async def complete_report_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Выполнить задачу в отчёте"""
    task = await complete_task_logic(task_id, current_user.id, db)
    return ReportTaskResponse(
        id=task.id,
        user_id=task.user_id,
        description=task.description,
        completed=task.completed,
        completed_at=task.completed_at
    )
