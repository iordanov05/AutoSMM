from fastapi import FastAPI
from app.api.users import router as users_router
from app.api.posts import router as posts_router
from app.api.groups import router as group_router

app = FastAPI()

# Подключаем API-маршруты
app.include_router(users_router, prefix="/users", tags=["Пользователи"])
app.include_router(posts_router, prefix="/posts", tags=["Посты"])
app.include_router(group_router, prefix="/groups", tags=["Группы"])

@app.get("/")
def root():
    return {"message": "Добро пожаловать в AutoSMM!"}
