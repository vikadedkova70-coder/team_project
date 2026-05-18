from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CheckinCreateRequest(BaseModel):
    """Создание check-in"""
    week_start_date: datetime
    content: Optional[str] = None


class CheckinTaskRequest(BaseModel):
    """Добавление задачи в check-in"""
    user_id: int
    description: str


class CheckinTaskResponse(BaseModel):
    """Задача check-in"""
    id: int
    user_id: int
    description: str
    completed: bool
    completed_at: Optional[datetime] = None


class CheckinResponse(BaseModel):
    """Check-in"""
    id: int
    team_id: int
    week_start_date: datetime
    content: Optional[str] = None
    created_by: int
    created_at: datetime
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    status: str
    tasks: list[CheckinTaskResponse]


class CheckinListResponse(BaseModel):
    """Список check-ins"""
    checkins: list[CheckinResponse]
    total: int
