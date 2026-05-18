from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class TeamActivityLog(Base):
    """История изменения рейтинга команды (для активностей)"""
    __tablename__ = "team_activity_logs"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    old_rating = Column(Float, nullable=False)
    new_rating = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    team = relationship("Team", back_populates="activity_logs")


class Activity(Base):
    """Событие в ленте активностей"""
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    event_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # team_activities commented out to avoid circular dependency issues in tests
    # team = relationship("Team", back_populates="activities")
    # user_activities commented out to avoid circular dependency issues in tests
    # user = relationship("User", back_populates="activities")


class Challenge(Base):
    """Задание от организаторов"""
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    reward_points = Column(Integer, default=0)
    deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    enrollments = relationship("TeamChallenge", back_populates="challenge")


class TeamChallenge(Base):
    """Запись о записи команды на челлендж"""
    __tablename__ = "team_challenges"

    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    status = Column(String(20), default="active", nullable=False)
    enrolled_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    challenge = relationship("Challenge", back_populates="enrollments")
    team = relationship("Team", back_populates="challenge_enrollments")