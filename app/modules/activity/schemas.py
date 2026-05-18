from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


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


class ActivityFeedResponse(BaseModel):
    """Лента активностей"""
    activities: list[ActivityResponse]
    total: int
