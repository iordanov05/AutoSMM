from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.rag import save_group_data, generate_post_from_context
from pydantic import BaseModel
from typing import List

router = APIRouter()

#  Модели для приёма JSON из ВК
class PostData(BaseModel):
    id: int
    date: str
    text: str
    hashtags: List[str]
    likes: int
    comments: int
    reposts: int

class ProductData(BaseModel):
    id: int
    name: str
    description: str
    price: str

class ServiceData(BaseModel):
    id: int
    name: str
    description: str
    price: str

class CommunityData(BaseModel):
    id: int
    name: str
    description: str
    category: str
    subscribers_count: int
    sections: List[str]

class VKGroupData(BaseModel):
    community: CommunityData
    posts: List[PostData]
    products: List[ProductData]
    services: List[ServiceData]

# 📌 Эндпоинт для сохранения данных группы
@router.post("/save_vk_data")
def save_vk_data(data: VKGroupData, db: Session = Depends(get_db)):
    return save_group_data(db, data)
