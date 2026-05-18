from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class RatingUpdateRequest(BaseModel):
    """Запрос на обновление компонентов КРК"""
    base: Optional[float] = Field(None, ge=0)
    unity: Optional[float] = Field(None, ge=0)
    bonus: Optional[float] = Field(None, ge=0)
    penalty: Optional[float] = Field(None, le=0)
    description: Optional[str] = None


class PenaltyRequest(BaseModel):
    """Запрос на применение штрафа"""
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=500)


class AdminOverwriteRequest(BaseModel):
    """Запрос на ручную корректировку КРК администратором"""
    new_total: float
    base: Optional[float] = None
    unity: Optional[float] = None
    bonus: Optional[float] = None
    penalty: Optional[float] = None
    reason: str = Field(..., min_length=1, max_length=1000)


class RatingResponse(BaseModel):
    """Ответ с данными рейтинга пользователя"""
    user_id: int
    base_score: float
    unity_score: float
    bonus_score: float
    penalty_score: float
    total_krk: float
    global_rank: int
    league: str
    rank_change: int
    updated_at: datetime

    class Config:
        from_attributes = True


class RankingItemResponse(BaseModel):
    """Элемент списка рейтинга"""
    user_id: int
    username: str
    total_krk: float
    global_rank: int
    league: str
    rank_change: int
    team_name: Optional[str] = None


class LeaderboardResponse(BaseModel):
    """Ответ глобального лидерборда"""
    rankings: List[RankingItemResponse]
    current_user_rank: Optional[int] = None
    current_user_rating: Optional[RatingResponse] = None
    total: int
    limit: int
    offset: int


class TopUsersResponse(BaseModel):
    """ТОП-N пользователей"""
    users: List[RankingItemResponse]


class TeamRatingResponse(BaseModel):
    """Рейтинг команды"""
    team_id: int
    team_name: str
    average_krk: float
    member_count: int
    global_rank: int
    rank_change: int

    class Config:
        from_attributes = True


class TeamLeaderboardResponse(BaseModel):
    """Лидерборд команд"""
    teams: List[TeamRatingResponse]
    total: int


class LeagueDistributionResponse(BaseModel):
    """Распределение по лигам"""
    newbie_count: int
    pro_count: int
    legend_count: int
    newbie_threshold: float = 0.0
    pro_threshold: float = 50.0
    legend_threshold: float = 100.0


class RatingHistoryItem(BaseModel):
    """Элемент истории изменений рейтинга"""
    id: int
    event_type: str
    old_total: float
    new_total: float
    description: Optional[str]
    created_at: datetime
    admin_username: Optional[str] = None


class RatingHistoryResponse(BaseModel):
    """История изменений рейтинга пользователя"""
    user_id: int
    logs: List[RatingHistoryItem]
    total: int


class PeriodArchiveRequest(BaseModel):
    """Запрос архивации периода"""
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)


class PeriodArchiveResponse(BaseModel):
    """Ответ архивации"""
    period_year: int
    period_month: int
    archived_count: int