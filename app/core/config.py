import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Читаем параметры из .env
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")
DB_HOST = os.getenv("DB_HOST")

# Добавьте SECRET_KEY
SECRET_KEY = os.getenv("SECRET_KEY")  
ALGORITHM = os.getenv("ALGORITHM")

# Получаем API-ключ DeepSeek
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH")
AI_MODEL = os.getenv("AI_MODEL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# Формируем строку подключения
DATABASE_URL = f"postgresql+psycopg2://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Конфигурация VK API
ACCESS_TOKEN=os.getenv("ACCESS_TOKEN")
API_VERSION=os.getenv("API_VERSION")
