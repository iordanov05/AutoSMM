from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.rag import generate_post_from_context
from app.models.user import User
from app.models.group import Group  
from app.api.auth import get_current_user

router = APIRouter()

@router.post("/generate")
def generate_post(
    user_query: str = Query(..., description="Запрос пользователя для генерации поста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Генерирует новый пост на основе данных о группе и пожеланий пользователя.
    """
    user_group = db.query(Group).filter(Group.user_id == current_user.id).first()
    if not user_group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    # Генерируем пост без истории (history можно передать пустой строкой)
    return {"generated_post": generate_post_from_context(db, user_query, user_group.id, history="")}

# Вспомогательное хранилище диалогов для WebSocket (в памяти)
user_sessions = {}

@router.websocket("/ws/{group_id}")
async def websocket_endpoint(websocket: WebSocket, group_id: int, db: Session = Depends(get_db)):
    """
    WebSocket-соединение для общения с ботом.
    Информация о пользователе извлекается из токена.
    """
    # Извлекаем токен из заголовка Authorization
    auth_header = websocket.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        await websocket.close(code=1008)
        return

    token = auth_header.split(" ")[1]

    try:
        current_user = get_current_user(token=token, db=db)
    except Exception as e:
        await websocket.close(code=4403)
        return

    user_id = current_user.id
    session_key = (user_id, group_id)
    if session_key not in user_sessions:
        user_sessions[session_key] = ""

    await websocket.accept()

    try:
        while True:
            message = await websocket.receive_text()
            # Добавляем новое сообщение в историю диалога
            user_sessions[session_key] += f"\nUser: {message}"
            response = generate_post_from_context(db, message, group_id, history=user_sessions[session_key])
            user_sessions[session_key] += f"\nAssistant: {response}"
            await websocket.send_text(response)
    except WebSocketDisconnect:
        # Можно добавить логирование отключения
        pass

