from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserProfileResponse(BaseModel):
    """Ответ с данными профиля пользователя"""
    username: str
    student_id: int
    full_name: str
    role: str
    team_name: Optional[str] = None
    team_id: Optional[int] = None


class TeamCreateRequest(BaseModel):
    """Запрос на создание команды"""
    name: str = Field(..., min_length=3, max_length=50)
    description: Optional[str] = Field(None, max_length=500)


class TeamResponse(BaseModel):
    """Информация о команде"""
    id: int
    name: str
    description: Optional[str] = None
    captain_id: int
    captain_name: Optional[str] = None
    members_count: int = 0
    created_at: datetime


class InviteLinkCreateRequest(BaseModel):
    """Создание пригласительной ссылки"""
    expires_hours: Optional[int] = 24
    max_uses: Optional[int] = None


class InviteLinkResponse(BaseModel):
    """Информация о пригласительной ссылке"""
    token: str
    team_name: str
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    uses_count: int = 0
    is_active: bool = True


class JoinByLinkRequest(BaseModel):
    """Вступление по пригласительной ссылке"""
    token: str


class JoinRequestResponse(BaseModel):
    """Информация о заявке"""
    id: int
    user_id: int
    username: str
    full_name: str
    status: str
    created_at: datetime


class JoinRequestAction(BaseModel):
    """Действие с заявкой"""
    action: str


class TeamUpdateRequest(BaseModel):
    """Обновление команды"""
    name: Optional[str] = Field(None, min_length=3, max_length=50)
    description: Optional[str] = Field(None, max_length=500)


class TeamMemberResponse(BaseModel):
    """Участник команды"""
    user_id: int
    username: str
    full_name: str
    joined_at: datetime


class TeamDetailResponse(BaseModel):
    """Детали команды"""
    id: int
    name: str
    description: Optional[str] = None
    captain_id: int
    captain_name: Optional[str] = None
    members: list[TeamMemberResponse]
    members_count: int
    created_at: datetime


class InviteLinkListResponse(BaseModel):
    """Список пригласительных ссылок"""
    links: list[InviteLinkResponse]
