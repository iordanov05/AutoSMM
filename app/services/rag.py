import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.post import Post
from app.models.group import Group
from app.models.product import Product
from app.models.service import Service
from app.models.user_group_association import UserGroupAssociation
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from app.core.config import CHROMA_DB_PATH, AI_MODEL, OPENROUTER_API_KEY

logger = logging.getLogger(__name__)

llm = ChatOpenAI(
    openai_api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model_name=AI_MODEL,
    temperature=0.5,
    max_tokens=3000
)

def get_group_vectorstore(vk_group_id: int) -> Chroma:
    collection_name = f"group_{vk_group_id}"
    vectorstore = Chroma(
        persist_directory=CHROMA_DB_PATH,
        collection_name=collection_name,
        embedding_function=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )
    try:
        vectorstore.get()
    except ValueError:
        logger.warning(f"⚠️ Коллекция {collection_name} не найдена! Создаем новую...")
        vectorstore.reset_collection()
    return vectorstore


def save_group_data(db: Session, user_id: int, data: dict):
    vk_group_id = data["community"].get("id")
    if not vk_group_id:
        logger.error("❌ Не найден vk_group_id в данных сообщества!")
        return {"status": "error", "message": "Ошибка: отсутствует vk_group_id"}

    last_uploaded_at = datetime.now(timezone.utc)

    # 🔁 Обновление или создание группы
    group = db.query(Group).filter(Group.vk_group_id == vk_group_id).first()
    if not group:
        group = Group(vk_group_id=vk_group_id)
        db.add(group)

    group.name = data["community"]["name"]
    group.description = data["community"].get("description")
    group.subscribers_count = data["community"].get("subscribers_count")
    db.commit()
    db.refresh(group)

    # 🔁 Обновление связи пользователя и группы
    association = db.query(UserGroupAssociation).filter(
        UserGroupAssociation.user_id == user_id,
        UserGroupAssociation.vk_group_id == vk_group_id
    ).first()
    if not association:
        association = UserGroupAssociation(user_id=user_id, vk_group_id=vk_group_id)
        db.add(association)
    association.last_uploaded_at = last_uploaded_at
    db.commit()

    # ❌ Удаляем старые посты/товары/услуги
    db.query(Post).filter(Post.group_id == vk_group_id).delete()
    db.query(Product).filter(Product.group_id == vk_group_id).delete()
    db.query(Service).filter(Service.group_id == vk_group_id).delete()
    db.commit()

    # ✅ Добавляем посты
    for post in data["posts"]:
        db.add(Post(
            group_id=vk_group_id,
            text=post["text"].strip(),
            likes=post.get("likes", 0),
            comments=post.get("comments", 0),
            reposts=post.get("reposts", 0)
        ))

    # ✅ Добавляем товары
    for product in data["products"]:
        db.add(Product(
            group_id=vk_group_id,
            name=product["name"].strip(),
            description=product.get("description", "").strip(),
            price=product.get("price", "Не указано")
        ))

    # ✅ Добавляем услуги
    for service in data["services"]:
        db.add(Service(
            group_id=vk_group_id,
            name=service["name"].strip(),
            description=service.get("description", "").strip(),
            price=service.get("price", "Не указано")
        ))

    db.commit()

    # 🧠 Обновляем ChromaDB
    logger.info("🧠 Обновляем коллекцию ChromaDB для группы...")
    vectorstore = get_group_vectorstore(vk_group_id)
    vectorstore.reset_collection()

    # 📄 Собираем документы
    posts = db.query(Post).filter(Post.group_id == vk_group_id).all()
    products = db.query(Product).filter(Product.group_id == vk_group_id).all()
    services = db.query(Service).filter(Service.group_id == vk_group_id).all()

    doc_description = f"Название группы: {group.name}\nОписание: {group.description}\nПодписчики: {group.subscribers_count}"
    doc_products = "Товары:\n" + "\n".join([f"{p.name} - {p.description} (Цена: {p.price})" for p in products]) if products else "Нет товаров."
    doc_services = "Услуги:\n" + "\n".join([f"{s.name} - {s.description} (Цена: {s.price})" for s in services]) if services else "Нет услуг."
    doc_posts = "Примеры постов:\n" + "\n\n".join([f"📝 {p.text}" for p in posts[-5:]]) if posts else "Нет постов."

    documents = [
        Document(page_content=doc_description, metadata={"type": "description", "vk_group_id": vk_group_id}),
        Document(page_content=doc_products, metadata={"type": "products", "vk_group_id": vk_group_id}),
        Document(page_content=doc_services, metadata={"type": "services", "vk_group_id": vk_group_id}),
        Document(page_content=doc_posts, metadata={"type": "posts", "vk_group_id": vk_group_id}),
    ]

    vectorstore.add_documents(documents)

    logger.info(f"✅ Данные о группе {vk_group_id} сохранены в PostgreSQL и ChromaDB.")

    return {
        "status": "success",
        "message": "✅ Данные обновлены и сохранены",
        "group": {
            "id": vk_group_id,
            "name": group.name,
            "description": group.description,
            "subscribers_count": group.subscribers_count,
            "last_uploaded_at": last_uploaded_at.isoformat()
        }
    }


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
