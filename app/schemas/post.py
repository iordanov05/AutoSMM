from pydantic import BaseModel
from typing import Optional

class PostCreate(BaseModel):
    user_id: int
    group_id: Optional[int]
    text: str
    likes: int = 0
    comments: int = 0
    reposts: int = 0

class PostResponse(PostCreate):
    id: int
