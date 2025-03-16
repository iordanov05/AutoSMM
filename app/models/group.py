from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    vk_group_id = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String, nullable=True)
    subscribers_count = Column(Integer, nullable=True)

# Импортируем User, Post, Product и Service в КОНЦЕ, когда `Group` уже загружен
from app.models.user import User
from app.models.post import Post
from app.models.product import Product
from app.models.service import Service

Group.user = relationship("User", back_populates="groups")
Group.posts = relationship("Post", back_populates="group", cascade="all, delete-orphan")
Group.products = relationship("Product", back_populates="group", cascade="all, delete-orphan")
Group.services = relationship("Service", back_populates="group", cascade="all, delete-orphan")
