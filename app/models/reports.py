from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class TeamReport(Base):
    """Отчёт команды"""
    __tablename__ = "team_reports"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_approved = Column(Boolean, default=False)

    files = relationship("ReportFile", back_populates="report", cascade="all, delete-orphan")
    tasks = relationship("ReportTask", back_populates="report", cascade="all, delete-orphan")


class ReportFile(Base):
    """Файл отчёта"""
    __tablename__ = "report_files"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("team_reports.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String, default="application/octet-stream")

    report = relationship("TeamReport", back_populates="files")


class ReportTask(Base):
    """Задача внутри отчёта — кто что делал"""
    __tablename__ = "report_tasks"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("team_reports.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    report = relationship("TeamReport", back_populates="tasks")
    user = relationship("User", back_populates="report_tasks")


class TeamEvent(Base):
    """Событие / воркшоп"""
    __tablename__ = "team_events"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(50), default="workshop")
    format = Column(String(20), default="online")
    location = Column(String(200), nullable=True)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=True)
    max_participants = Column(Integer, nullable=True)
    is_public = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    invitations = relationship("EventInvitation", back_populates="event", cascade="all, delete-orphan")
    participants = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")


class EventInvitation(Base):
    """Приглашение команде на событие"""
    __tablename__ = "event_invitations"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("team_events.id"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    status = Column(String(20), default="pending")
    responded_at = Column(DateTime, nullable=True)

    event = relationship("TeamEvent", back_populates="invitations")


class EventParticipant(Base):
    """Участник события (зарегистрировавшийся)"""
    __tablename__ = "event_participants"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("team_events.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    registered_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("TeamEvent", back_populates="participants")


class WeeklyCheckin(Base):
    """Еженедельный check-in"""
    __tablename__ = "weekly_checkins"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    week_start_date = Column(DateTime, nullable=False)
    content = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")

    tasks = relationship("CheckinTask", back_populates="checkin", cascade="all, delete-orphan")


class CheckinTask(Base):
    """Задача в check-in — кто что делал за неделю"""
    __tablename__ = "checkin_tasks"

    id = Column(Integer, primary_key=True, index=True)
    checkin_id = Column(Integer, ForeignKey("weekly_checkins.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    description = Column(Text, nullable=False)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    checkin = relationship("WeeklyCheckin", back_populates="tasks")
    user = relationship("User", back_populates="checkin_tasks")


class HelpRequest(Base):
    """Заявка на помощь"""
    __tablename__ = "help_requests"

    id = Column(Integer, primary_key=True, index=True)
    requesting_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    help_type = Column(String(20), default="receiving")
    format = Column(String(20), default="both")
    estimated_effort_hours = Column(Integer, nullable=True)
    status = Column(String(20), default="open")
    created_at = Column(DateTime, default=datetime.utcnow)
    fulfilled_by_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    fulfilled_at = Column(DateTime, nullable=True)

    responses = relationship("HelpResponse", back_populates="request", cascade="all, delete-orphan")


class HelpResponse(Base):
    """Отклик на заявку помощи"""
    __tablename__ = "help_responses"

    id = Column(Integer, primary_key=True, index=True)
    help_request_id = Column(Integer, ForeignKey("help_requests.id"), nullable=False, index=True)
    responding_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    message = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    responded_at = Column(DateTime, nullable=True)

    request = relationship("HelpRequest", back_populates="responses")
