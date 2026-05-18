from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class HelpRequestCreate(BaseModel):
    """Создание заявки на помощь"""
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    help_type: str = Field(default="receiving")
    format: str = Field(default="both")
    estimated_effort_hours: Optional[int] = Field(None, ge=1)


class HelpResponseCreate(BaseModel):
    """Отклик на заявку"""
    message: Optional[str] = None


class HelpRequestResponse(BaseModel):
    """Заявка на помощь"""
    id: int
    requesting_team_id: int
    title: str
    description: Optional[str] = None
    help_type: str
    format: str
    estimated_effort_hours: Optional[int] = None
    status: str
    created_at: datetime
    fulfilled_by_team_id: Optional[int] = None
    fulfilled_at: Optional[datetime] = None


class HelpResponseResponse(BaseModel):
    """Отклик"""
    id: int
    help_request_id: int
    responding_team_id: int
    message: Optional[str] = None
    status: str
    responded_at: Optional[datetime] = None


class HelpRequestDetailResponse(HelpRequestResponse):
    """Заявка с откликами"""
    responses: list[HelpResponseResponse] = []


class HelpListResponse(BaseModel):
    """Список заявок"""
    requests: list[HelpRequestResponse]
    total: int
