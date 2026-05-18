from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class PostImageResponse(BaseModel):
    """Информация об изображении"""
    id: int
    filename: str
    file_path: str
    file_size: int
    content_type: str
    uploaded_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PostCreateRequest(BaseModel):
    """Запрос на создание поста"""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=10000)


class PostUpdateRequest(BaseModel):
    """Запрос на обновление поста"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1, max_length=10000)


class PostAuthorInfo(BaseModel):
    """Информация об авторе поста"""
    username: str
    full_name: str


class PostTeamInfo(BaseModel):
    """Информация о команде автора"""
    id: int
    name: str


class PostResponse(BaseModel):
    """Ответ с данными поста"""
    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    author: PostAuthorInfo
    team: Optional[PostTeamInfo] = None
    images: List[PostImageResponse] = []
    model_config = ConfigDict(from_attributes=True)


class PostListResponse(BaseModel):
    """Список постов"""
    posts: List[PostResponse]
    total: int
