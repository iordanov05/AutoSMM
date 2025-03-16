from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.rag import save_group_data
from app.models.user import User
from app.api.auth import get_current_user

router = APIRouter()

@router.post("/save")
def save_group_data_endpoint(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Сохраняет данные о группе, постах, продуктах и услугах.
    """
    return save_group_data(db, current_user.id, data)
