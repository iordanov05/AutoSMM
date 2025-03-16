from fastapi import FastAPI
from app.api.users import router as users_router
from app.api.posts import router as posts_router 

app = FastAPI()

# Подключаем API-маршруты
app.include_router(users_router, prefix="/users", tags=["Пользователи"])
app.include_router(posts_router, prefix="/posts", tags=["Посты"])  

@app.get("/")
def root():
    return {"message": "Добро пожаловать в AutoSMM!"}
