from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ChallengeResponse(BaseModel):
    """Челлендж"""
    id: int
    title: str
    description: Optional[str] = None
    reward_points: int
    deadline: Optional[datetime] = None
    created_at: datetime
    is_active: bool


class ChallengeCreateRequest(BaseModel):
    """Создание челленджа"""
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    reward_points: int = Field(default=0, ge=0)
    deadline: Optional[datetime] = None


class TeamChallengeResponse(BaseModel):
    """Запись команды о прохождении челленджа"""
    id: int
    challenge: ChallengeResponse
    team_id: int
    status: str
    enrolled_at: datetime
    completed_at: Optional[datetime] = None


class EnrollmentAction(BaseModel):
    """Действие с записью"""
    action: str
