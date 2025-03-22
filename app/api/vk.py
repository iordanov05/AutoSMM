from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.services.vk_service import get_community_data, get_community_data_by_id
from app.services.group_utils import  generate_fake_group_id
from app.services.vk_service import save_group_data
from app.core.db import get_db
from app.models.user import User
from app.api.auth import get_current_user

router = APIRouter()

class VirtualGroupCreate(BaseModel):
    name: str
    description: str = ""
    category: str = ""

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


@router.post("/update_community_data")
def update_community_data(
    community_id: int = Query(..., description="ID сообщества ВКонтакте"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Обновляет данные сообщества ВКонтакте по его ID и сохраняет их в базу.
    """
    data = get_community_data_by_id(community_id)
    if not data:
        raise HTTPException(status_code=400, detail="Не удалось получить данные из сообщества")

    return save_group_data(db, current_user.id, data)


@router.post("/create_virtual_group")
def create_virtual_group(
    group: VirtualGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Создаёт несуществующее сообщество с отрицательным ID.
    """
    fake_id = generate_fake_group_id(db)

    data = {
        "community": {
            "id": fake_id,
            "name": group.name,
            "description": group.description,
            "category": group.category,
            "subscribers_count": 0
        },
        "posts": [],
        "products": [],
        "services": []
    }

    return save_group_data(db, current_user.id, data)