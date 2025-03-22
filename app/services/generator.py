import logging
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI
from app.models import Group, Post, Product, Service
from app.services.rag import get_group_vectorstore
from app.core.config import OPENROUTER_API_KEY, AI_MODEL

logger = logging.getLogger(__name__)

llm = ChatOpenAI(
    openai_api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model_name=AI_MODEL,
    temperature=0.5,
    max_tokens=3000
)


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
        У нас нет данных о группе.  
        Прежде чем создать рекламный пост, уточни у пользователя ключевую информацию:  
        - О чём эта группа?  
        - Какие товары или услуги она продвигает?  
        - Какой стиль общения в постах предпочтителен? (формальный, дружеский, экспертный)  
        - Есть ли примеры прошлых постов или рекламных текстов?  

        Запроси только то, что критически важно для создания качественного поста.  
        После получения данных сразу сгенерируй публикацию.
        """
        
    prompt = f"""
    Ты — профессиональный маркетолог и копирайтер. Ты изучил группу ВКонтакте и её стиль общения. 
    Теперь ты отвечаешь на запрос пользователя, придерживаясь стиля и структуры, которые уже используются в этой группе.

    🔹 **История общения (для понимания запроса пользователя)**:  
    {history}

    🔹 **Данные о группе (используй как контекст)**:  
    {context_texts}

    🔹 **Что написал пользователь**:  
    "{query}"

    🔎 Твоя задача — понять, что именно хочет пользователь:
    - Если он просит «привет», «что ты умеешь» и т.п. — вежливо объясни, что ты можешь помочь с созданием постов для сообщества, которое ты уже изучил (вставь его название), и предложи задать тему поста.
    - Если он просит не рекламный пост, а, например, «сделай описание группы» — выполни запрос в нужной форме.
    - Если он просит сгенерировать пост — выполни это, строго соблюдая стиль и структуру прошлых публикаций!

    ⚠️ **Внимание**: если тебе нужно создать пост, но в контексте слишком мало информации (например, не указано, о чём группа, какие услуги она продвигает или какой стиль у постов), **не придумывай ничего** и **вежливо попроси у пользователя конкретные уточнения**:
    - Что за группа и чем занимается?
    - Какие услуги или товары нужно продвигать?
    - Какой стиль постов нужен (формальный, дружеский, экспертный)?
    - Есть ли примеры предыдущих публикаций?
        
    🎯 Когда создаёшь пост, обязательно:
    1. **Проанализируй стиль прошлых постов**:
        - Были ли там эмодзи? Если нет — не используй.
        - Были ли подзаголовки или разбивка на блоки? Если нет — не делай.
        - Было ли обращение на «вы» или «ты»? Повтори стиль.
        - Какой был тон — дружелюбный, экспертный, нейтральный?

    2. **Подбери правильный объём**:
        - Если посты были короткими — пиши кратко и по делу.
        - Если были длинными — можешь развернуться.
        - Если нет примеров — выбери подходящий стиль на своё усмотрение.

    3. **Используй только те товары и услуги, которые есть в данных. Не выдумывай.**

    4. **Всегда добавляй призыв к действию**, если это уместно: купить, подписаться, задать вопрос.

    5. **Не объясняй свои шаги. Пиши сразу как живой текст — будто ты SMM-менеджер, пишущий пост для сообщества.**
    """


    
    logger.info(f"📢 [vk_group_id={vk_group_id}] Передаем запрос в {AI_MODEL}:\n{prompt}")

    response = llm.invoke(prompt)
    return response.content.strip()

def generate_ideas_for_group(db: Session, group_id: int) -> str:
    """
    Генерирует 5 актуальных идей и готовых постов для сообщества, основываясь на полном анализе его данных.
    """
    posts = db.query(Post).filter(Post.group_id == group_id).all()
    group = db.query(Group).filter(Group.vk_group_id == group_id).first()
    products = db.query(Product).filter(Product.group_id == group_id).all()
    services = db.query(Service).filter(Service.group_id == group_id).all()

    formatted_posts = "\n\n".join([
        f"📝 {p.text}\n👍 {p.likes} 💬 {p.comments} 🔁 {p.reposts}" for p in posts
    ]) or "Нет постов."

    doc_description = f"Название группы: {group.name}\nОписание: {group.description}\nПодписчики: {group.subscribers_count}"
    doc_products = "\n".join([f"{p.name} — {p.description} (Цена: {p.price})" for p in products]) or "Нет товаров."
    doc_services = "\n".join([f"{s.name} — {s.description} (Цена: {s.price})" for s in services]) or "Нет услуг."
    last_post_date = posts[-1].date.strftime('%d.%m.%Y') if posts else "Нет постов"

    prompt = f"""
Ты — креативный копирайтер и маркетолог. Твоя задача — полностью проанализировать сообщество ВКонтакте и предложить 5 самых актуальных тем для новых постов.

🎯 Используй ВСЕ предоставленные данные, включая:
- Посты (и их активность: лайки, комментарии, репосты)
- Товары и услуги
- Название и описание группы
- Подписчиков
- Дату последней публикации: {last_post_date}
- Текущую дату (если актуально — учти праздники или события)

🔍 Проанализируй:
1. Основную тематику группы — о чём она?
2. Какие посты пользовались наибольшей популярностью?
3. Какие товары/услуги могут быть актуальны сейчас?
4. Когда последний раз публиковался пост?

💡 На основе анализа:
1. Предложи **5 тем** для публикации, которые **будут максимально уместны сейчас**.
2. Для каждой темы объясни, **почему она подходит** (временная актуальность, популярность тематики, подходящий товар, давно не было такой темы и т.п.).
3. Сразу напиши пост под каждую идею.
4. Не используй выдуманные товары, услуги или тематики — только на основе фактов выше.
5. Соблюдай стиль прошлых постов: оформление, объём, наличие/отсутствие эмодзи, обращения и т.д.
6. Не пиши анализ группы, не вводи текст типа "Анализ:..." — сразу переходи к 5 идеям, их обоснованию и текстам постов.


📋 Данные о группе:
{doc_description}

📦 Товары:
{doc_products}

🛠 Услуги:
{doc_services}

📜 Примеры постов с активностью:
{formatted_posts}

🎁 Итог:
Предложи 5 идей для постов, объясни каждую, и сразу приведи сам текст публикации.
    """.strip()

    logger.info(f"⚡ Генерация по команде 'auto_idea' (vk_group_id={group_id})")
    logger.debug(prompt)

    response = llm.invoke(prompt)
    return response.content.strip()

def generate_growth_plan_for_group(db: Session, group_id: int) -> str:
    """
    Генерирует подробный анализ сообщества и стратегический план его развития.
    """
    posts = db.query(Post).filter(Post.group_id == group_id).all()
    group = db.query(Group).filter(Group.vk_group_id == group_id).first()
    products = db.query(Product).filter(Product.group_id == group_id).all()
    services = db.query(Service).filter(Service.group_id == group_id).all()

    formatted_posts = "\n\n".join([
        f"📝 {p.text}\n👍 {p.likes} 💬 {p.comments} 🔁 {p.reposts}" for p in posts
    ]) or "Нет постов."

    doc_description = f"Название группы: {group.name}\nОписание: {group.description}\nПодписчики: {group.subscribers_count}"
    doc_products = "\n".join([f"{p.name} — {p.description} (Цена: {p.price})" for p in products]) or "Нет товаров."
    doc_services = "\n".join([f"{s.name} — {s.description} (Цена: {s.price})" for s in services]) or "Нет услуг."
    last_post_date = posts[-1].date.strftime('%d.%m.%Y') if posts else "Нет постов"

    prompt = f"""
Ты — лучший в мире специалист по продвижению сообществ ВКонтакте. Сейчас тебе предстоит провести **глубокий анализ** сообщества и выдать **план развития**, который реально поможет ему вырасти.

🎯 Данные сообщества:
- Название: {group.name}
- Описание: {group.description}
- Подписчиков: {group.subscribers_count}
- Дата последнего поста: {last_post_date}
- Примеры товаров: {doc_products}
- Примеры услуг: {doc_services}
- Примеры постов с активностью:  
{formatted_posts}

🔍 Что ты должен сделать:
1. Проанализируй тематику сообщества — о чём оно, чем полезно подписчикам.
2. Проанализируй товары и услуги: какие предложения стоит продвигать.
3. Проанализируй посты:
   - Частота публикаций (редко/часто, есть ли регулярность).
   - Какие посты наиболее популярны (по лайкам, репостам, комментам).
   - Какой стиль оформления используется (эмодзи, обращения, структура).

📈 В результате:
Сделай вывод, как сейчас обстоят дела в сообществе, и предложи **конкретный стратегический план развития**:

- Какие темы постов стоит публиковать в ближайший месяц.
- Какую частоту постинга ты рекомендуешь (учти текущую активность).
- В какие дни и время лучше публиковать.
- Какие товары и услуги лучше всего продвигать (если они есть).
- Какие форматы использовать (истории, опросы, розыгрыши, экспертные посты и т.д.).
- Если нужно — порекомендуй обновить описание группы, название и т.д.

🎯 Главное:
Пиши конкретно и по делу. Без воды. Будто ты маркетолог, пришедший с чётким аудитом и планом. Говори от первого лица.

🚫 Не пиши "анализ: ..." и "вывод: ..." — просто выдай текст как итоговый профессиональный отчёт с понятными рекомендациями.
    """.strip()

    logger.info(f"📊 Генерация плана развития (vk_group_id={group_id})")
    logger.debug(prompt)

    response = llm.invoke(prompt)
    return response.content.strip()

