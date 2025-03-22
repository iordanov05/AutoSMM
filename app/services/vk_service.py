import re
import requests
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from langchain_core.documents import Document
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from app.models import Group, Post, Product, Service, UserGroupAssociation
from app.services.rag import get_group_vectorstore
from app.core.config import ACCESS_TOKEN, API_VERSION

logger = logging.getLogger(__name__)


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
    group.category = data["community"].get("category")
    
    
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
    post_docs = [
    Document(
        page_content=f"📝 {p.text}",
        metadata={"type": "post", "vk_group_id": vk_group_id}
    )
    for p in posts[-15:]
    ]
    
    documents = [
    Document(page_content=doc_description, metadata={"type": "description", "vk_group_id": vk_group_id}),
    Document(page_content=doc_products, metadata={"type": "products", "vk_group_id": vk_group_id}),
    Document(page_content=doc_services, metadata={"type": "services", "vk_group_id": vk_group_id}),
    ] + post_docs


    vectorstore.add_documents(documents)

    logger.info(f"✅ Данные о группе {vk_group_id} сохранены в PostgreSQL и ChromaDB.")

    return {
        "status": "success",
        "message": "✅ Данные обновлены и сохранены",
        "group": {
            "vk_group_id": vk_group_id,
            "name": group.name,
            "description": group.description,
            "category": group.category,
            "subscribers_count": group.subscribers_count,
            "last_uploaded_at": last_uploaded_at.isoformat()
        }
    }



def get_community_data(community_link: str) -> dict:
    community_id = get_community_id_from_link(community_link)
    if not community_id:
        return None
    return get_community_data_by_id(community_id)


def get_community_data_by_id(community_id: int) -> dict:
    """
    Получает данные о сообществе ВКонтакте, используя его ID.
    """
    community_info = get_community_info(community_id)
    if not community_info:
        return None  # Если сообщество не найдено, ничего не возвращаем

    return {
        'community': community_info,
        'posts': get_community_posts(community_id),
        'products': parse_market_with_selenium(community_id),
        'services': parse_services_with_selenium(community_id)
    }


def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Без UI
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--disable-blink-features=AutomationControlled")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def get_community_id_from_link(community_link: str) -> str:
    match = re.search(r"vk\.com/([\w\d_.-]+)", community_link)
    if not match:
        print("Ошибка: Некорректная ссылка.")
        return None
    screen_name = match.group(1)
    if screen_name.isdigit():
        return screen_name
    url = "https://api.vk.com/method/utils.resolveScreenName"
    params = {
        "access_token": ACCESS_TOKEN,
        "v": API_VERSION,
        "screen_name": screen_name
    }
    response = requests.get(url, params=params).json()
    if "error" in response:
        print(f"Ошибка VK API: {response['error']['error_msg']}")
        return None
    if "response" in response and response["response"]:
        return str(response["response"]["object_id"])
    print("Ошибка: Сообщество не найдено.")
    return None


def get_community_info(community_id: str) -> dict:
    url = 'https://api.vk.com/method/groups.getById'
    params = {
        'access_token': ACCESS_TOKEN,
        'v': API_VERSION,
        'group_id': community_id,
        'fields': 'description,members_count'
    }
    response = requests.get(url, params=params).json()
    if 'error' in response:
        print(f"Ошибка при получении информации о сообществе: {response['error']['error_msg']}")
        return None
    community_data = response['response'][0]
    return {
        'id': community_id,
        'name': community_data['name'],
        'description': community_data.get('description', ''),
        'subscribers_count': community_data.get('members_count', 0)
    }
    
    
def get_community_posts(community_id: str) -> list:
    url = 'https://api.vk.com/method/wall.get'
    params = {
        'access_token': ACCESS_TOKEN,
        'v': API_VERSION,
        'owner_id': f'-{community_id}',
        'count': 15  #  Берем всегда последние 15 постов
    }
    response = requests.get(url, params=params).json()

    if 'error' in response:
        print(f"Ошибка при получении постов: {response['error']['error_msg']}")
        return []

    posts = response['response']['items']
    filtered_posts = []

    for post in posts:
        post_date = datetime.fromtimestamp(post['date'])
        text = post.get('text', '').strip()
        has_attachments = 'attachments' in post

        # 1️⃣ Обрабатываем репосты
        if 'copy_history' in post:
            text = "[Репост другого поста]"

        # 2️⃣ Пост без текста, но с медиа
        elif not text and has_attachments:
            attachments = post['attachments']
            if any(att['type'] == 'photo' for att in attachments):
                text = "[Пост без текста: изображение]"
            elif any(att['type'] == 'video' for att in attachments):
                text = "[Пост без текста: видео]"
            else:
                text = "[Пост без текста]"

        # 3️⃣ Абсолютно пустой пост — пропускаем
        elif not text:
            continue

        filtered_posts.append({
            'date': post_date.isoformat(),
            'text': text,
            'hashtags': [tag for tag in text.split() if tag.startswith('#')],
            'likes': post.get('likes', {}).get('count', 0),
            'comments': post.get('comments', {}).get('count', 0),
            'reposts': post.get('reposts', {}).get('count', 0)
        })

    return filtered_posts


def parse_market_with_selenium(group_id: str) -> list:
    driver = get_driver()
    try:
        community_url = f'https://vk.com/market-{group_id}?screen=group'
        driver.get(community_url)

        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "market_row"))
            )
        except Exception:
            print("Нет товаров")
            return []

        products = []
        links = [item.find_element(By.TAG_NAME, 'a').get_attribute('href')
                 for item in driver.find_elements(By.CLASS_NAME, "market_row")]

        for link in links[:15]:
            driver.get(link)
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@data-testid="market_item_page_title"]'))
                )
                title = driver.find_element(By.XPATH, '//*[@data-testid="market_item_page_title"]').text.strip()
                price = driver.find_element(By.XPATH, '//*[@data-testid="market_item_page_price"]').text.strip()
                description = driver.find_element(By.XPATH, '//*[@data-testid="showmoretext-in"]').text.strip()
                products.append({
                    "name": title,
                    "description": description,
                    "price": price
                })
            except Exception as e:
                print(f"Ошибка при сборе данных: {e}")

        return products
    finally:
        driver.quit()


def parse_services_with_selenium(group_id: str) -> list:
    driver = get_driver()
    try:
        community_url = f'https://vk.com/uslugi-{group_id}?screen=group'
        driver.get(community_url)

        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "market_row"))
            )
        except Exception:
            print("Нет услуг")
            return []

        services = []
        links = [item.find_element(By.TAG_NAME, 'a').get_attribute('href')
                 for item in driver.find_elements(By.CLASS_NAME, "market_row")]

        for link in links[:15]:
            driver.get(link)
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@data-testid="market_item_page_title"]'))
                )
                title = driver.find_element(By.XPATH, '//*[@data-testid="market_item_page_title"]').text.strip()
                price = driver.find_element(By.XPATH, '//*[@data-testid="market_item_page_price"]').text.strip()
                description = driver.find_element(By.XPATH, '//*[@data-testid="showmoretext-in"]').text.strip()
                services.append({
                    "name": title,
                    "description": description,
                    "price": price
                })
            except Exception as e:
                print(f"Ошибка при сборе данных: {e}")

        return services
    finally:
        driver.quit()
