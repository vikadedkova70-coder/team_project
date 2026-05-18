from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class Post(Base):
    """Модель поста"""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    author = relationship("User", foreign_keys=[author_id], lazy="select")

    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    team = relationship("Team", foreign_keys=[team_id], lazy="select")

    images = relationship("PostImage", back_populates="post", cascade="all, delete-orphan", lazy="select")


class PostImage(Base):
    """Модель изображения поста"""
    __tablename__ = "post_images"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String, default="image/jpeg")
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    post = relationship("Post", back_populates="images", lazy="select")
