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



@router.delete("/user_groups/{vk_group_id}")
def delete_user_group_association(
    vk_group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Удаляет связь пользователя и группы ВКонтакте.
    Если у группы больше нет пользователей, она автоматически удаляется (см. SQLAlchemy event).
    """
    user_id = current_user.id

    # Проверяем, есть ли связь пользователя с этой группой
    association = db.query(UserGroupAssociation).filter(
        UserGroupAssociation.user_id == user_id,
        UserGroupAssociation.vk_group_id == vk_group_id
    ).first()

    if not association:
        raise HTTPException(status_code=404, detail="Связь пользователя с группой не найдена")

    # Удаляем связь
    db.delete(association)
    db.commit()

    return {"message": f"Пользователь {user_id} успешно отвязан от группы {vk_group_id}"}
