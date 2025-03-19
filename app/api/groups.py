from typing import List
from fastapi import APIRouter, Depends, HTTPException
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

# Pydantic модель для возврата JSON
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

    # Получаем все связи пользователя с группами, сортируем по last_uploaded_at
    group_associations = (
        db.query(UserGroupAssociation)
        .filter(UserGroupAssociation.user_id == user_id)
        .order_by(desc(UserGroupAssociation.last_uploaded_at))
        .all()
    )

    # Извлекаем ID групп и даты загрузки
    group_data = {assoc.vk_group_id: assoc.last_uploaded_at for assoc in group_associations}

    if not group_data:
        raise HTTPException(status_code=404, detail="У пользователя нет связанных групп.")

    # Получаем сами группы по их ID
    groups = db.query(Group).filter(Group.vk_group_id.in_(group_data.keys())).all()

    # Формируем JSON-ответ
    response = [
        GroupResponse(
            vk_group_id=group.vk_group_id,
            name=group.name,
            description=group.description,
            category=group.category,
            subscribers_count=group.subscribers_count,
            last_uploaded_at=group_data[group.vk_group_id]  # Берем дату загрузки из ассоциации
        )
        for group in groups
    ]

    return response
