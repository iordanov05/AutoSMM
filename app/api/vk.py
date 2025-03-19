from pydantic import BaseModel
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.services.vk_service import get_community_data
from app.services.rag import save_group_data
from app.core.db import get_db
from app.models.user import User
from app.api.auth import get_current_user

router = APIRouter()


@router.post("/parse_and_save")
def parse_and_save_vk(
    community_link: str = Query(..., description="Ссылка на сообщество ВКонтакте"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Парсит данные сообщества ВКонтакте и сохраняет их в базу.
    """
    data = get_community_data(community_link)
    if not data:
        raise HTTPException(status_code=400, detail="Не удалось получить данные из сообщества")
    # Функция сохранения ожидает, что в data["community"] присутствует поле "id"
    if "id" not in data["community"]:
        raise HTTPException(status_code=400, detail="Не удалось определить ID сообщества")
    return save_group_data(db, current_user.id, data)
