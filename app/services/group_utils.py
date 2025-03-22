from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.group import Group

def generate_fake_group_id(db: Session) -> int:
    """
    Генерирует уникальный отрицательный ID для несуществующего сообщества.
    """
    min_id = db.query(func.min(Group.vk_group_id)).filter(Group.vk_group_id < 0).scalar()
    return min_id - 1 if min_id is not None else -1
