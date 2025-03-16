from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.rag import save_group_data, generate_post_from_context
from app.models.user import User
from app.api.auth import get_current_user 
from app.models.group import Group  

router = APIRouter()

@router.post("/save")
def save_data(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Сохраняет данные о группе, постах, продуктах и услугах.
    """
    return save_group_data(db, current_user.id, data)  



@router.post("/generate")
def generate_post(
    user_query: str = Query(..., description="Запрос пользователя для генерации поста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Генерирует новый пост на основе истории группы, товаров, услуг и пожеланий пользователя.
    """
    user_group = db.query(Group).filter(Group.user_id == current_user.id).first()
    if not user_group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    return {"generated_post": generate_post_from_context(db, user_query, user_group.id)}