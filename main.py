from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.users import router as users_router
from app.api.posts import router as posts_router
from app.api.groups import router as groups_router 
from app.api.vk import router as vk_router
import os
import app.core.events  # Импортируем, чтобы обработчики событий зарегистрировались
os.environ["TOKENIZERS_PARALLELISM"] = "false" 
app = FastAPI()

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Можно ограничить список доменов, если нужно
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем API-маршруты
app.include_router(users_router, prefix="/users", tags=["Пользователи"])
app.include_router(posts_router, prefix="/posts", tags=["Посты"])
app.include_router(groups_router, prefix="/groups", tags=["Группы"])
app.include_router(vk_router, prefix="/vk", tags=["VK"])

@app.get("/")
def root():
    return {"message": "Добро пожаловать в AutoSMM!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8855, reload=True)
