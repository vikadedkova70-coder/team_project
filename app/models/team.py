from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class Team(Base):
    """Модель команды"""
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    captain_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    rating = Column(Float, default=3.0, nullable=False)

    captain = relationship("User", back_populates="team_captain")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    invite_links = relationship("TeamInviteLink", back_populates="team", cascade="all, delete-orphan")
    join_requests = relationship("TeamJoinRequest", back_populates="team", cascade="all, delete-orphan")
    rating_rel = relationship("TeamRating", back_populates="team", uselist=False, cascade="all, delete-orphan")
    activity_logs = relationship("TeamActivityLog", back_populates="team", cascade="all, delete-orphan", foreign_keys="TeamActivityLog.team_id")
    # activities commented out to avoid circular dependency issues in tests
    # activities = relationship("Activity", back_populates="team", cascade="all, delete-orphan", foreign_keys="Activity.team_id")
    challenge_enrollments = relationship("TeamChallenge", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    """Участник команды"""
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="team_membership")
    team = relationship("Team", back_populates="members")


class TeamInviteLink(Base):
    """Пригласительная ссылка в команду"""
    __tablename__ = "team_invite_links"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True, nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    max_uses = Column(Integer, nullable=True)
    uses_count = Column(Integer, default=0)

    team = relationship("Team", back_populates="invite_links")


class TeamJoinRequest(Base):
    """Заявка на вступление в команду"""
    __tablename__ = "team_join_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="pending")

    team = relationship("Team", back_populates="join_requests")

    # team_posts = relationship("Post", back_populates="team")