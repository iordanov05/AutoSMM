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
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# Формируем строку подключения
DATABASE_URL = f"postgresql+psycopg2://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

