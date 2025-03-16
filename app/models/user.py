from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)

# ✅ Импортируем Group и Post в самом КОНЦЕ, когда `User` уже загружен
from app.models.group import Group
from app.models.post import Post

User.groups = relationship("Group", back_populates="user", cascade="all, delete-orphan")
User.posts = relationship("Post", back_populates="user", cascade="all, delete-orphan")
