import logging
from sqlalchemy.orm import Session
from app.models.post import Post
from app.models.group import Group
from app.models.product import Product
from app.models.service import Service
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from app.core.config import CHROMA_DB_PATH, DEEPSEEK_MODEL, OPENROUTER_API_KEY

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация ChromaDB
vectorstore = Chroma(
    persist_directory=CHROMA_DB_PATH,
    embedding_function=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
)
try:
    vectorstore.get()
except ValueError:
    logger.warning("⚠️ Коллекция ChromaDB не найдена! Пересоздаём...")
    vectorstore.reset_collection()

# Подключаем DeepSeek через OpenRouter
llm = ChatOpenAI(
    openai_api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model_name=DEEPSEEK_MODEL,
    temperature=0.5,
    max_tokens=1000
)

def save_group_data(db: Session, user_id: int, data: dict):
    """
    Сохраняет данные о группе, постах, товарах и услугах в PostgreSQL и ChromaDB.
    """
    group = db.query(Group).filter(
        Group.vk_group_id == data["community"]["id"],
        Group.user_id == user_id
    ).first()

    if not group:
        group = Group(
            user_id=user_id,
            vk_group_id=data["community"]["id"],
            name=data["community"]["name"],
            description=data["community"]["description"],
            subscribers_count=data["community"]["subscribers_count"],
            category=data["community"]["category"],
        )
        db.add(group)
        db.commit()
        db.refresh(group)

    # Очищаем дубликаты постов, товаров и услуг перед добавлением
    existing_posts = {p.text for p in db.query(Post).filter(Post.group_id == group.id).all()}
    existing_products = {p.name for p in db.query(Product).filter(Product.group_id == group.id).all()}
    existing_services = {s.name for s in db.query(Service).filter(Service.group_id == group.id).all()}

    # Добавляем новые посты
    for post in data["posts"]:
        if post["text"] not in existing_posts:
            new_post = Post(
                user_id=user_id,
                group_id=group.id,
                text=post["text"],
                likes=post["likes"],
                comments=post["comments"],
                reposts=post["reposts"],
            )
            db.add(new_post)

    # Добавляем новые товары
    for product in data["products"]:
        if product["name"] not in existing_products:
            new_product = Product(
                group_id=group.id,
                name=product["name"],
                description=product["description"],
                price=product["price"],
            )
            db.add(new_product)

    # Добавляем новые услуги
    for service in data["services"]:
        if service["name"] not in existing_services:
            new_service = Service(
                group_id=group.id,
                name=service["name"],
                description=service["description"],
                price=service["price"],
            )
            db.add(new_service)

    db.commit()

    # Группируем данные для ChromaDB
    past_posts = db.query(Post).filter(Post.group_id == group.id).all()
    post_styles = "\n\n".join([f"📝 {p.text}" for p in past_posts[-5:]]) if past_posts else "Нет записанных постов."

    products = db.query(Product).filter(Product.group_id == group.id).all()
    services = db.query(Service).filter(Service.group_id == group.id).all()

    context_data = f"""
    Название группы: {group.name}
    Описание: {group.description}
    Подписчики: {group.subscribers_count}
    Категория: {group.category}

    Товары:
    """ + "\n".join([f"{p.name} - {p.description} (Цена: {p.price})" for p in products]) + """

    Услуги:
    """ + "\n".join([f"{s.name} - {s.description} (Цена: {s.price})" for s in services]) + """

    Стилизация прошлых постов:
    """ + post_styles

    logger.info("🗑️ Удаляем старые данные из ChromaDB...")
    vectorstore.reset_collection()

    document = Document(
        page_content=context_data,
        metadata={"group_id": group.id}
    )
    vectorstore.add_documents([document])

    logger.info("✅ Данные о группе, товарах и услугах сохранены в ChromaDB!")
    logger.info(f"📌 Сохранённый контекст:\n{context_data}")

    return {"message": "✅ Данные сохранены в базе"}

def generate_post_from_context(db: Session, query: str, group_id: int, history: str = "") -> str:
    """
    Генерирует пост с учетом (опциональной) истории диалога и данных из ChromaDB.
    """
    retriever = vectorstore.as_retriever()

    try:
        results = retriever.invoke(query)
    except ValueError:
        logger.error(f"⚠️ Ошибка! ChromaDB не найдена или пустая для group_id={group_id}.")
        return "Ошибка: нет данных в ChromaDB."

    unique_results = list(set([res.page_content for res in results]))
    context_texts = "\n\n".join(unique_results)

    prompt = f"""
    Ты — эксперт по маркетингу. Напиши рекламный пост с учетом прошлых постов, данных о группе и истории общения.
    
    🔹 История общения:
    {history}

    🔹 Данные о группе:
    {context_texts}

    🔹 Пользователь хочет: "{query}"

    ❗ Анализируй стиль оформления прошлых постов, используй контактные данные, оформление, хештеги и тон общения.
    ❗ Добавляй только реальные товары и услуги из списка.
    ❗ Пиши пост без команд и пояснений, только сам текст.
    """

    logger.info(f"📢 [group_id={group_id}] Передаём запрос в DeepSeek...")
    logger.debug(f"Запрос:\n{prompt}")

    response = llm.invoke(prompt)
    return response.content.strip()
