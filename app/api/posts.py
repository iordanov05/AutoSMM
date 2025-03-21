from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.rag import generate_post_from_context, generate_ideas_for_group, generate_growth_plan_for_group
from app.api.auth import get_current_user

router = APIRouter()

# Вспомогательное хранилище диалогов для WebSocket (в памяти)
user_sessions = {}

@router.websocket("/ws/{group_id}")
async def websocket_endpoint(websocket: WebSocket, group_id: int, db: Session = Depends(get_db)):
    """
    WebSocket-соединение для общения с ботом.
    Токен пользователя передаётся через query (?token=...).
    """
    # 👉 Получаем токен из query параметров
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)  # Policy Violation
        return

    try:
        current_user = get_current_user(token=token, db=db)
    except Exception:
        await websocket.close(code=4403)  # Forbidden
        return

    user_id = current_user.id
    session_key = (user_id, group_id)
    if session_key not in user_sessions:
        user_sessions[session_key] = ""

    await websocket.accept()

    try:
        while True:
            message = await websocket.receive_text()

            # Обработка спец-команды "Придумай сам"
            if message == "auto_idea":
                result = generate_ideas_for_group(db, group_id)
                user_sessions[session_key] += f"\nAssistant: {result}"
                await websocket.send_text(result)
                continue
            
            if message == "growth_plan":
                result = generate_growth_plan_for_group(db, group_id)
                user_sessions[session_key] += f"\nAssistant: {result}"
                await websocket.send_text(result)
                continue


            # 🧠 Обычное взаимодействие
            user_sessions[session_key] += f"\nUser: {message}"
            response = generate_post_from_context(db, message, group_id, history=user_sessions[session_key])
            user_sessions[session_key] += f"\nAssistant: {response}"
            await websocket.send_text(response)

    except WebSocketDisconnect:
        pass
