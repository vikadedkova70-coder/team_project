from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RatingLogResponse(BaseModel):
    """Запись изменения рейтинга"""
    id: int
    event_type: str
    old_rating: float
    new_rating: float
    description: Optional[str] = None
    created_at: datetime


class ActivityResponse(BaseModel):
    """Событие активности"""
    id: int
    team_id: int
    user_id: Optional[int] = None
    event_type: str
    title: str
    description: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime


class TeamProfileResponse(BaseModel):
    """Профиль команды"""
    id: int
    name: str
    description: Optional[str] = None
    captain_id: int
    captain_name: Optional[str] = None
    members_count: int
    rating: float
    rating_history: list[RatingLogResponse]
    recent_activities: list[ActivityResponse]
    created_at: datetime
