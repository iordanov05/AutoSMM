import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.post import Post
from app.models.group import Group
from app.models.product import Product
from app.models.service import Service
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from app.models.user_group_association import UserGroupAssociation
from app.core.config import CHROMA_DB_PATH, AI_MODEL, OPENROUTER_API_KEY

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация LLM
llm = ChatOpenAI(
    openai_api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model_name=AI_MODEL,
    temperature=0.5,
    max_tokens=3000
)

def save_group_data(db: Session, user_id: int, data: dict):
    """
    Сохраняет данные о группе, постах, товарах и услугах в PostgreSQL и индексирует информацию в ChromaDB.
    """
    last_uploaded_at = datetime.now(timezone.utc)

    vk_group_id = data["community"].get("id")
    if not vk_group_id:
        logger.error("Не найден vk_group_id в данных сообщества!")
        return {"status": "error", "message": "Ошибка: отсутствует vk_group_id"}
    
    group = db.query(Group).filter(Group.vk_group_id == vk_group_id).first()

    if not group:
        group = Group(
            vk_group_id=vk_group_id,
            name=data["community"]["name"],
            description=data["community"].get("description"),
            category=data["community"].get("category"),
            subscribers_count=data["community"].get("subscribers_count"),
        )
        db.add(group)
        db.commit()
        db.refresh(group)

    association = db.query(UserGroupAssociation).filter(
        UserGroupAssociation.user_id == user_id,
        UserGroupAssociation.vk_group_id == vk_group_id
    ).first()

    if not association:
        association = UserGroupAssociation(
            user_id=user_id,
            vk_group_id=vk_group_id,
            last_uploaded_at=last_uploaded_at
        )
        db.add(association)
    else:
        association.last_uploaded_at = last_uploaded_at

    db.commit()

    # 🚀 Сохраняем посты
    existing_posts = {p.text for p in db.query(Post).filter(Post.group_id == vk_group_id).all()}
    
    for post in data["posts"]:
        text = post["text"].strip()

        if text not in existing_posts:
            new_post = Post(
                group_id=vk_group_id,
                text=text,
                likes=post.get("likes", 0),
                comments=post.get("comments", 0),
                reposts=post.get("reposts", 0),
            )
            db.add(new_post)

    # ✅ **Сохраняем товары (products)**
    existing_products = {p.name for p in db.query(Product).filter(Product.group_id == vk_group_id).all()}
    
    for product in data["products"]:
        name = product["name"].strip()
        if name not in existing_products:
            new_product = Product(
                group_id=vk_group_id,
                name=name,
                description=product.get("description", "").strip(),
                price=product.get("price", "Не указано")
            )
            db.add(new_product)

    # ✅ **Сохраняем услуги (services)**
    existing_services = {s.name for s in db.query(Service).filter(Service.group_id == vk_group_id).all()}
    
    for service in data["services"]:
        name = service["name"].strip()
        if name not in existing_services:
            new_service = Service(
                group_id=vk_group_id,
                name=name,
                description=service.get("description", "").strip(),
                price=service.get("price", "Не указано")
            )
            db.add(new_service)

    db.commit()

    return {
        "status": "success",
        "message": "✅ Данные сохранены в базе",
        "group": {
            "vk_group_id": vk_group_id,
            "name": group.name,
            "description": group.description,
            "category": group.category,
            "subscribers_count": group.subscribers_count,
            "last_uploaded_at": last_uploaded_at.isoformat()
        }
    }


def get_group_vectorstore(vk_group_id: int) -> Chroma:
    """
    Создает и возвращает экземпляр ChromaDB для сообщества с уникальным именем коллекции, основанным на vk_group_id.
    """
    collection_name = f"group_{vk_group_id}"
    vectorstore = Chroma(
        persist_directory=CHROMA_DB_PATH,
        collection_name=collection_name,
        embedding_function=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )
    try:
        # Проверяем, существует ли коллекция
        vectorstore.get()
    except ValueError:
        logger.warning(f"⚠️ Коллекция {collection_name} не найдена! Создаем новую...")
        vectorstore.reset_collection()
    return vectorstore

def generate_post_from_context(db: Session, query: str, vk_group_id: int, history: str = "") -> str:
    """
    Генерирует пост на основе данных из коллекции ChromaDB для сообщества.
    Если поиск по запросу не возвращает документов, выполняется fallback-поиск по пустому запросу.
    """
    vectorstore = get_group_vectorstore(vk_group_id)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    
    try:
        results = retriever.invoke(query)
        docs = results if isinstance(results, list) else [results]
        logger.info(f"Найдено документов: {len(docs)} для запроса: {query}")
    except Exception as e:
        logger.error(f"Ошибка поиска в коллекции для vk_group_id {vk_group_id}: {e}")
        docs = []
    
    if not docs or all(not doc.page_content.strip() for doc in docs):
        logger.warning(f"Нет релевантных документов для vk_group_id {vk_group_id} по запросу: {query}. Используем fallback.")
        try:
            fallback_results = retriever.invoke("")
            docs = fallback_results if isinstance(fallback_results, list) else [fallback_results]
            logger.info(f"Fallback найдено документов: {len(docs)}")
        except Exception as e:
            logger.error(f"Ошибка fallback поиска: {e}")
            docs = []
    
    context_texts = "\n\n".join([doc.page_content for doc in docs if doc.page_content.strip()])
    if not context_texts.strip():
        context_texts = """
        ❗ У нас нет данных о группе.  
        Прежде чем создать рекламный пост, уточни у пользователя ключевую информацию:  
        - О чем эта группа?  
        - Какие товары или услуги она продвигает?  
        - Какой стиль общения в постах предпочтителен? (формальный, дружеский, экспертный)  
        - Есть ли примеры прошлых постов или рекламных текстов?  

        Запроси только то, что критически важно для создания качественного поста.  
        После получения данных сразу сгенерируй публикацию.
        """
    
    prompt = f"""
    Ты — эксперт по маркетингу и копирайтингу. Твоя задача — написать рекламный пост в стиле прошлых публикаций группы.

    🔹 **История общения (для понимания предпочтений аудитории)**:  
    {history}

    🔹 **Данные о группе (важно учитывать при написании поста)**:  
    {context_texts}

    🔹 **Пользователь хочет**:  
    "{query}"

    📌 **Твои задачи**:  
    1️) **Соблюдай стиль прошлых постов**, если они есть — анализируй их структуру, тон общения, оформление, хештеги, длину и контактные данные.  
    2️) **Если старых постов нет**, **сам определи** оптимальный объем и стиль публикации в зависимости от тематики, типа контента и целевой аудитории группы.  
    3️) **Используй только актуальные товары и услуги** — не добавляй ничего, чего нет в группе.  
    4️) **Делай текст живым и вовлекающим** — он должен привлекать внимание аудитории.  
    5️) **Добавь призыв к действию** — мотивируй подписаться, купить, оставить комментарий или задать вопрос.  
    6️) **Ориентируйся на объем прошлых постов**:  
    - Если раньше посты были короткие, сделай краткий и лаконичный текст.  
    - Если в группе преобладают длинные посты, пиши развернуто.  
    - **Если старых постов нет — оцени ситуацию самостоятельно и выбери лучший вариант.**  
    7️) **Не используй команды и пояснения, не расписывай свои шаги** — сразу пиши готовый рекламный пост.

    📣 **Генерируй пост как живой текст, будто его написал SMM-менеджер группы.**  
    """

    
    logger.info(f"📢 [vk_group_id={vk_group_id}] Передаем запрос в {AI_MODEL}:\n{prompt}")

    response = llm.invoke(prompt)
    return response.content.strip()
