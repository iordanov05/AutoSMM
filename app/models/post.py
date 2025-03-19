from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.db import Base
from datetime import datetime

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.vk_group_id", ondelete="CASCADE"), nullable=False)
    text = Column(String, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    reposts = Column(Integer, default=0)

    group = relationship("Group", back_populates="posts")
