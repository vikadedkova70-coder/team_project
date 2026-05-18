from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ReportCreateRequest(BaseModel):
    """Создание отчёта"""
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    challenge_id: Optional[int] = None


class ReportFileResponse(BaseModel):
    """Файл отчёта"""
    id: int
    filename: str
    file_size: int
    content_type: str
    uploaded_at: datetime


class ReportTaskAssignRequest(BaseModel):
    """Назначение задачи"""
    user_id: int
    description: str


class ReportTaskResponse(BaseModel):
    """Задача в отчёте"""
    id: int
    user_id: int
    description: str
    completed: bool
    completed_at: Optional[datetime] = None


class ReportResponse(BaseModel):
    """Отчёт"""
    id: int
    team_id: int
    challenge_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    created_by: int
    created_at: datetime
    is_approved: bool
    files: list[ReportFileResponse]
    tasks: list[ReportTaskResponse]
