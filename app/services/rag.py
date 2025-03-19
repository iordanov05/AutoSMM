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
from app.models.user_group_association import UserGroupAssociation
from app.core.config import CHROMA_DB_PATH, DEEPSEEK_MODEL, OPENROUTER_API_KEY

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация LLM
llm = ChatOpenAI(
    openai_api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model_name=DEEPSEEK_MODEL,
    temperature=0.5,
    max_tokens=3000
)


def save_group_data(db: Session, user_id: int, data: dict):
    """
    Сохраняет данные о группе, постах, товарах и услугах в PostgreSQL и индексирует информацию в ChromaDB.
    """
    # Проверяем наличие vk_group_id
    vk_group_id = data["community"].get("id")
    if not vk_group_id:
        logger.error("Не найден vk_group_id в данных сообщества!")
        return {"status": "error", "message": "Ошибка: отсутствует vk_group_id"}
    
    # Проверяем, существует ли группа
    group = db.query(Group).filter(Group.vk_group_id == vk_group_id).first()

    # Если группа не существует, создаем новую
    if not group:
        group = Group(
            vk_group_id=vk_group_id,
            name=data["community"]["name"],
            description=data["community"].get("description"),
            subscribers_count=data["community"].get("subscribers_count"),
        )
        db.add(group)
        db.commit()
        db.refresh(group)

    # Проверяем, есть ли связь пользователя с этой группой
    association = db.query(UserGroupAssociation).filter(
        UserGroupAssociation.user_id == user_id,
        UserGroupAssociation.vk_group_id == vk_group_id
    ).first()

    if not association:
        association = UserGroupAssociation(user_id=user_id, vk_group_id=vk_group_id)
        db.add(association)
        db.commit()

    # Извлекаем уже сохраненные записи, чтобы избежать дублирования
    existing_posts = {p.text for p in db.query(Post).filter(Post.group_id == vk_group_id).all()}
    existing_products = {p.name for p in db.query(Product).filter(Product.group_id == vk_group_id).all()}
    existing_services = {s.name for s in db.query(Service).filter(Service.group_id == vk_group_id).all()}

    # Сохраняем новые посты
    for post in data["posts"]:
        if post["text"] not in existing_posts:
            new_post = Post(
                group_id=vk_group_id,
                text=post["text"],
                likes=post.get("likes", 0),
                comments=post.get("comments", 0),
                reposts=post.get("reposts", 0),
            )
            db.add(new_post)

    # Сохраняем новые товары
    for product in data["products"]:
        if product["name"] not in existing_products:
            new_product = Product(
                group_id=vk_group_id,
                name=product["name"],
                description=product.get("description"),
                price=product.get("price"),
            )
            db.add(new_product)

    # Сохраняем новые услуги
    for service in data["services"]:
        if service["name"] not in existing_services:
            new_service = Service(
                group_id=vk_group_id,
                name=service["name"],
                description=service.get("description"),
                price=service.get("price"),
            )
            db.add(new_service)

    db.commit()

    # Формируем данные для ChromaDB
    past_posts = db.query(Post).filter(Post.group_id == vk_group_id).all()
    post_styles = "\n\n".join([f"📝 {p.text}" for p in past_posts[-5:]]) if past_posts else "Нет записанных постов."

    products_list = db.query(Product).filter(Product.group_id == vk_group_id).all()
    services_list = db.query(Service).filter(Service.group_id == vk_group_id).all()

    doc_description = f"Название группы: {group.name}\nОписание: {group.description}\nПодписчики: {group.subscribers_count}"
    doc_products = "Товары:\n" + ("\n".join([f"{p.name} - {p.description} (Цена: {p.price})" for p in products_list]) if products_list else "Нет товаров.")
    doc_services = "Услуги:\n" + ("\n".join([f"{s.name} - {s.description} (Цена: {s.price})" for s in services_list]) if services_list else "Нет услуг.")
    doc_posts = "Стилизация прошлых постов:\n" + post_styles

    documents = [
        Document(page_content=doc_description, metadata={"vk_group_id": vk_group_id, "type": "description"}),
        Document(page_content=doc_products, metadata={"vk_group_id": vk_group_id, "type": "products"}),
        Document(page_content=doc_services, metadata={"vk_group_id": vk_group_id, "type": "services"}),
        Document(page_content=doc_posts, metadata={"vk_group_id": vk_group_id, "type": "posts"}),
    ]

    # Сброс и добавление новых данных в ChromaDB
    logger.info("🗑️ Очищаем данные в коллекции для группы...")
    group_vectorstore = get_group_vectorstore(vk_group_id)
    group_vectorstore.reset_collection()
    group_vectorstore.add_documents(documents)

    full_context = "\n\n".join([doc.page_content for doc in documents])
    logger.info(f"✅ Данные о группе (vk_group_id={vk_group_id}) сохранены в ChromaDB!")
    logger.info(f"📌 Сохранённый контекст:\n{full_context}")

    return {
        "status": "success",
        "message": "✅ Данные сохранены в базе",
        "group": {
            "id": vk_group_id,
            "name": group.name,
            "description": group.description,
            "subscribers_count": group.subscribers_count
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
    # Ищем больше документов (например, k=4) для получения контекста
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    
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
        context_texts = "Нет данных о группе, проверьте загрузку информации."
    
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
    
    logger.info(f"📢 [vk_group_id={vk_group_id}] Передаем запрос в DeepSeek:\n{prompt}")
    print(prompt)  # Для отладки
    response = llm.invoke(prompt)
    return response.content.strip()
