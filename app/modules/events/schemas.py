from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EventCreateRequest(BaseModel):
    """Создание события"""
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    event_type: str = Field(default="workshop")
    format: str = Field(default="online")
    location: Optional[str] = Field(None, max_length=200)
    starts_at: datetime
    ends_at: Optional[datetime] = None
    max_participants: Optional[int] = Field(None, ge=1)
    is_public: bool = True


class EventResponse(BaseModel):
    """Событие"""
    id: int
    team_id: int
    title: str
    description: Optional[str] = None
    event_type: str
    format: str
    location: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    max_participants: Optional[int] = None
    is_public: bool
    created_by: int
    created_at: datetime


class EventDetailResponse(EventResponse):
    """Событие с деталями"""
    invitations: list["EventInvitationResponse"] = []
    participants: list["EventParticipantResponse"] = []


class EventInvitationResponse(BaseModel):
    """Приглашение"""
    id: int
    event_id: int
    team_id: int
    status: str
    responded_at: Optional[datetime] = None


class EventParticipantResponse(BaseModel):
    """Участник события"""
    id: int
    event_id: int
    user_id: Optional[int] = None
    team_id: int
    registered_at: datetime


class InvitationRespondRequest(BaseModel):
    """Ответ на приглашение"""
    accept: bool
