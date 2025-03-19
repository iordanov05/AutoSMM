from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.db import Base

class Group(Base):
    __tablename__ = "groups"

    vk_group_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String, nullable=True)
    subscribers_count = Column(Integer, nullable=True)

    # Связи с постами, продуктами и услугами
    posts = relationship("Post", back_populates="group", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="group", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="group", cascade="all, delete-orphan")

    # Связь многие ко многим с пользователями
    user_associations = relationship("UserGroupAssociation", back_populates="group", cascade="all, delete-orphan")
