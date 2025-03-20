from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.core.db import get_db
from app.models.user import User
from app.models.group import Group
from app.models.user_group_association import UserGroupAssociation
from app.api.auth import get_current_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# Pydantic-модель для возврата JSON
class GroupResponse(BaseModel):
    vk_group_id: int
    name: str
    description: str | None
    category: str | None
    subscribers_count: int | None
    last_uploaded_at: datetime

@router.get("/user_groups", response_model=List[GroupResponse])
def get_user_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получает список всех групп, связанных с текущим пользователем, сортированных по последней загрузке.
    """
    user_id = current_user.id

    # Объединяем таблицы в одном запросе (используем JOIN)
    groups = (
        db.query(
            Group.vk_group_id,
            Group.name,
            Group.description,
            Group.category,
            Group.subscribers_count,
            UserGroupAssociation.last_uploaded_at
        )
        .join(UserGroupAssociation, UserGroupAssociation.vk_group_id == Group.vk_group_id)
        .filter(UserGroupAssociation.user_id == user_id)
        .order_by(desc(UserGroupAssociation.last_uploaded_at))  # Сортируем по дате обновления
        .all()
    )

    # Если у пользователя нет групп, возвращаем пустой массив
    return [
        GroupResponse(
            vk_group_id=g.vk_group_id,
            name=g.name,
            description=g.description,
            category=g.category,
            subscribers_count=g.subscribers_count,
            last_uploaded_at=g.last_uploaded_at
        )
        for g in groups
    ]
