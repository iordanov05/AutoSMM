# app/services/vk_service.py
import re
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from app.core.config import ACCESS_TOKEN, API_VERSION


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
    # Добавляем id в информацию о сообществе
    community_data["id"] = community_id
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
        'count': 20
    }
    response = requests.get(url, params=params).json()
    if 'error' in response:
        print(f"Ошибка при получении постов: {response['error']['error_msg']}")
        return []
    posts = response['response']['items']
    two_weeks_ago = datetime.now() - timedelta(days=30)
    filtered_posts = []
    for post in posts:
        post_date = datetime.fromtimestamp(post['date'])
        if post_date >= two_weeks_ago:
            filtered_posts.append({
                'date': post_date.isoformat(),
                'text': post['text'],
                'hashtags': [tag for tag in post['text'].split() if tag.startswith('#')],
                'likes': post['likes']['count'],
                'comments': post['comments']['count'],
                'reposts': post['reposts']['count']
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
        links = [item.find_element(By.TAG_NAME, 'a').get_attribute('href')
                 for item in driver.find_elements(By.CLASS_NAME, "market_row")]
        products = []
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
        links = [item.find_element(By.TAG_NAME, 'a').get_attribute('href')
                 for item in driver.find_elements(By.CLASS_NAME, "market_row")]
        services = []
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

def get_community_data(community_link: str) -> dict:
    community_id = get_community_id_from_link(community_link)
    if not community_id:
        return None
    community_info = get_community_info(community_id)
    posts = get_community_posts(community_id)
    products = parse_market_with_selenium(community_id)
    services = parse_services_with_selenium(community_id)
    return {
        'community': community_info,
        'posts': posts,
        'products': products,
        'services': services
    }
