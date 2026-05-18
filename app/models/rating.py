from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base
import enum


class LeagueTier(enum.Enum):
    """Уровни лиг"""
    NEWBIE = "newbie"      # 0 - 49.99 баллов
    PRO = "pro"            # 50 - 99.99 баллов
    LEGEND = "legend"      # 100+ баллов


class UserRating(Base):
    """Индивидуальный рейтинг пользователя (КРК)"""
    __tablename__ = "user_ratings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)

    # Компоненты формулы КРК
    base_score = Column(Float, default=0.0, nullable=False)      # Базовые баллы
    unity_score = Column(Float, default=0.0, nullable=False)     # Единство команды
    bonus_score = Column(Float, default=0.0, nullable=False)     # Бонусы
    penalty_score = Column(Float, default=0.0, nullable=False)   # Штрафы (отрицательные)

    # Итоговый КРК (вычисляемый)
    total_krk = Column(Float, default=0.0, nullable=False)

    # Позиция в рейтинге (кэшируется для производительности)
    global_rank = Column(Integer, default=0, index=True)

    # Лига
    league = Column(String, default=LeagueTier.NEWBIE.value, index=True)

    # Динамика (изменение за неделю)
    rank_change = Column(Integer, default=0)  # +1 вверх, -1 вниз, 0 без изменений

    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="rating")
    logs = relationship("RatingLog", back_populates="user", cascade="all, delete-orphan", primaryjoin="UserRating.id==RatingLog.user_id", foreign_keys="RatingLog.user_id")
    admin_overwrites = relationship("RatingAdminOverwrite", back_populates="user", cascade="all, delete-orphan", primaryjoin="UserRating.id==RatingAdminOverwrite.user_id", foreign_keys="RatingAdminOverwrite.user_id")


class RatingLog(Base):
    """История изменений рейтинга пользователя"""
    __tablename__ = "rating_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_ratings.id"), index=True, nullable=False)

    # Что изменилось
    old_base = Column(Float, nullable=True)
    new_base = Column(Float, nullable=True)
    old_unity = Column(Float, nullable=True)
    new_unity = Column(Float, nullable=True)
    old_bonus = Column(Float, nullable=True)
    new_bonus = Column(Float, nullable=True)
    old_penalty = Column(Float, nullable=True)
    new_penalty = Column(Float, nullable=True)
    old_total = Column(Float, nullable=False)
    new_total = Column(Float, nullable=False)

    # Причина изменения
    event_type = Column(String(50), nullable=False)  # activity, challenge, penalty, admin, transfer
    description = Column(Text, nullable=True)

    # Контекст
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Если изменение админом

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = relationship("UserRating", back_populates="logs")
    team = relationship("Team", primaryjoin="RatingLog.team_id==Team.id", foreign_keys=[team_id])
    admin_user = relationship("User", foreign_keys=[admin_user_id])


class RatingAdminOverwrite(Base):
    """Ручная корректировка КРК администратором"""
    __tablename__ = "rating_admin_overwrites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_ratings.id"), index=True, nullable=False)
    admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Новые значения (переопределяют автоматический расчет)
    new_base = Column(Float, nullable=True)
    new_unity = Column(Float, nullable=True)
    new_bonus = Column(Float, nullable=True)
    new_penalty = Column(Float, nullable=True)
    new_total = Column(Float, nullable=False)

    reason = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)  # Можно отключить overwrite

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("UserRating", back_populates="admin_overwrites")
    admin_user = relationship("User", foreign_keys=[admin_user_id])


class TeamRating(Base):
    """Командный КРК (среднее арифметическое участников)"""
    __tablename__ = "team_ratings"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), unique=True, index=True, nullable=False)

    average_krk = Column(Float, default=0.0, nullable=False)
    member_count = Column(Integer, default=0, nullable=False)

    global_rank = Column(Integer, default=0, index=True)
    rank_change = Column(Integer, default=0)

    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    team = relationship("Team", back_populates="rating_rel")
    logs = relationship("TeamRatingLog", back_populates="team_rating", cascade="all, delete-orphan")


class TeamRatingLog(Base):
    """История изменений командного рейтинга"""
    __tablename__ = "team_rating_logs"

    id = Column(Integer, primary_key=True, index=True)
    team_rating_id = Column(Integer, ForeignKey("team_ratings.id"), index=True, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True, nullable=False)

    old_average = Column(Float, nullable=False)
    new_average = Column(Float, nullable=False)
    old_member_count = Column(Integer, nullable=True)
    new_member_count = Column(Integer, nullable=True)

    # Причина
    event_type = Column(String(50), nullable=False)  # member_joined, member_left, member_rating_changed
    description = Column(Text, nullable=True)

    # Кто вызвал изменение
    affected_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    team_rating = relationship("TeamRating", back_populates="logs")
    team = relationship("Team", primaryjoin="TeamRatingLog.team_id==Team.id", foreign_keys=[team_id])
    affected_user = relationship("User")


class LeagueSettings(Base):
    """Настройки порогов лиг"""
    __tablename__ = "league_settings"

    id = Column(Integer, primary_key=True, index=True)
    tier = Column(String, unique=True, index=True, nullable=False)  # newbie, pro, legend

    min_score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=True)  # NULL для верхней лиги

    is_active = Column(Boolean, default=True)

    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class RatingPeriodArchive(Base):
    """Архив рейтингов за период (месяц)"""
    __tablename__ = "rating_period_archives"

    id = Column(Integer, primary_key=True, index=True)

    period_year = Column(Integer, nullable=False, index=True)
    period_month = Column(Integer, nullable=False, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True, nullable=True)

    final_krk = Column(Float, nullable=False)
    final_rank = Column(Integer, nullable=False)
    league = Column(String, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    team = relationship("Team")

    __table_args__ = (
        UniqueConstraint('period_year', 'period_month', 'user_id', name='uq_period_user'),
    )