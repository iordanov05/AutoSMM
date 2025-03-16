from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.db import Base
from datetime import datetime

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)  # ID поста
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # Привязка к пользователю
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True)  # Привязка к группе (если пост принадлежит группе)
    text = Column(String, nullable=False)  # Текст поста
    date = Column(DateTime, default=datetime.utcnow)  # Дата создания
    likes = Column(Integer, default=0)  # Количество лайков
    comments = Column(Integer, default=0)  # Количество комментариев
    reposts = Column(Integer, default=0)  # Количество репостов

    user = relationship("User", back_populates="posts")  # Связь с пользователем
    group = relationship("Group", back_populates="posts")  # Связь с группой (если пост относится
