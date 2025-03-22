from sqlalchemy import Column, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.core.db import Base

class UserGroupAssociation(Base):
    __tablename__ = "user_group_association"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    vk_group_id = Column(Integer, ForeignKey("groups.vk_group_id", ondelete="CASCADE"), primary_key=True)
    last_uploaded_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="user_group_associations")
    group = relationship("Group", back_populates="user_associations") 
