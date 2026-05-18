from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base
import enum


class UserRole(enum.Enum):
    """Роли пользователей"""
    STUDENT = "student"
    CAPTAIN = "captain"
    TEACHER = "teacher"
    ADMIN = "admin"


class Student(Base):
    """Модель студента (данные из вуза)"""
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    surname = Column(String, index=True)
    name = Column(String, index=True)
    patronymic = Column(String, index=True)

    user = relationship("User", back_populates="student", uselist=False)


class User(Base):
    """Модель аккаунта для входа в систему"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), unique=True, index=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    role = Column(String, default=UserRole.STUDENT.value)

    student = relationship("Student", back_populates="user")
    team_membership = relationship("TeamMember", back_populates="user", uselist=False)
    team_captain = relationship("Team", back_populates="captain", uselist=False)
    rating = relationship("UserRating", back_populates="user", uselist=False, cascade="all, delete-orphan")
    # activities relationship commented out to avoid circular dependency issues in tests
    # activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    report_tasks = relationship("ReportTask", back_populates="user", cascade="all, delete-orphan")
    checkin_tasks = relationship("CheckinTask", back_populates="user", cascade="all, delete-orphan")

    # author_posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")