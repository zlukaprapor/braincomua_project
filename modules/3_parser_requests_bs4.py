# import os
import time
import json
# import csv
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from load_django import *
from parser_app.models import Product

# Заголовки для requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Referer': 'https://www.google.com/',
    'Connection': 'keep-alive',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Upgrade-Insecure-Requests': '1',
    'DNT': '1',  # Do Not Track
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'TE': 'Trailers',  # Transfer Encoding
}

# ------------------ Утиліти ------------------
def _parse_price(text):
    """Витягує число з рядка і повертає Decimal або None."""
    if not text:
        return None
    m = re.search(r'[\d\s,\.]+', text)
    if not m:
        return None
    raw = m.group().strip()
    raw = raw.replace(' ', '').replace(',', '.')
    try:
        return Decimal(raw)
    except InvalidOperation:
        try:
            return Decimal(str(float(raw)))
        except Exception:
            return None

def _unique_preserve_order(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

# ------------------ PARSER ------------------
def parse_single_product(url, headers=HEADERS, timeout=12):
    """
    Парсить одну сторінку товару і повертає словник з можливими полями.
    Замінюй CSS-селектори на потрібні для цільового сайту.
    """
    product = {}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Не вдалось завантажити {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # посилання на джерело
    product['link'] = url

    # Полное название товара
    title = None
    if soup.select_one('h1'):
        title = soup.select_one('h1').get_text(strip=True)
    elif soup.select_one('.product-title'):
        title = soup.select_one('.product-title').get_text(strip=True)
    product['title'] = title
    product['full_name'] = title

    # Колір
    color = None
    for span in soup.select('.br-pr-chr-item span'):
        if span.get_text(strip=True) == 'Колір':
            next_span = span.find_next_sibling('span')
            if next_span:
                color = next_span.get_text(strip=True)
            break
    product['color'] = color

    # Объем памяти
    memory = None
    for span in soup.select('.br-pr-chr-item span'):
        if span.get_text(strip=True) == 'Вбудована пам\'ять':
            next_span = span.find_next_sibling('span')
            if next_span:
                memory = next_span.get_text(strip=True)
            break
    product['memory'] = memory

    # Продавец
    vendor = None
    v_sel = soup.select_one('.br-pr-del-type .delivery-target strong') # шукаємо конкретно блок з адресою магазину
    if v_sel:
        vendor = v_sel.get_text(strip=True)
    product['vendor'] = vendor

    # Цена
    # Основна ціна
    v_sel = soup.select_one('.br-pr-price.main-price-block .br-pr-np > div > span')
    price = _parse_price(v_sel.get_text(strip=True)) if v_sel else None
    product['price'] = price

    # Акційна ціна (якщо є)
    v_sel = soup.select_one('.br-pr-price.main-price-block .br-pr-np-hz > div > span')
    discount_price = _parse_price(v_sel.get_text(strip=True)) if v_sel else None
    product['discount_price'] = discount_price if discount_price else price

    # Все фото товара. Здесь нужно собрать ссылки на фото и сохранить в список
    photos = []

    for img in soup.select('img.dots-image'):
        src = img.get('data-big-picture-src') or img.get('src')
        if src:
            src = src.strip()
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = urljoin(url, src)
            elif not src.startswith('http'):
                src = urljoin(url, src)
            photos.append(src)

    # Видаляємо дублікати, зберігаючи порядок
    product['photos'] = _unique_preserve_order(photos)

    # Код товара
    code = None
    code_sel = soup.select_one('#product_code .br-pr-code-val')
    if code_sel:
        code = code_sel.get_text(strip=True)
    product['code'] = code

    # Кол-во отзывов
    reviews_count = 0  # default, якщо відгуків немає
    rev_sel = soup.select_one('a.scroll-to-element span')
    if rev_sel:
        try:
            reviews_count = int(rev_sel.get_text(strip=True))
        except ValueError:
            pass  # залишаємо 0, якщо текст не число
    product['reviews_count'] = reviews_count

    # Серия
    article = None
    for span in soup.select('.br-pr-chr-item span'):
        if span.get_text(strip=True) == 'Артикул':
            next_span = span.find_next_sibling('span')
            if next_span:
                article = next_span.get_text(strip=True)
            break
    product['article'] = article

    # Диагональ экрана
    diagonal = None
    for span in soup.select('.br-pr-chr-item span'):
        if span.get_text(strip=True) == 'Діагональ екрану':
            next_span = span.find_next_sibling('span')
            if next_span:
                diagonal = next_span.get_text(strip=True)
            break
    product['diagonal'] = diagonal

    # Разрешение дисплея
    resolution = None
    for span in soup.select('.br-pr-chr-item span'):
        if span.get_text(strip=True) == 'Роздільна здатність екрану':
            next_span = span.find_next_sibling('span')
            if next_span:
                resolution = next_span.get_text(strip=True)
            break
    product['resolution'] = resolution

    # Характеристики товара. Все характеристики на вкладке. Характеристики собрать как словарь
    specifications = {}

    for item in soup.select('.br-pr-chr-item'):
        for row in item.select('div > div'):
            key_span = row.find('span')
            value_span = key_span.find_next_sibling('span') if key_span else None
            if key_span and value_span:
                # Беремо текст, очищаємо пробіли та коми
                key = key_span.get_text(strip=True)
                # Можливо у значенні є <a> або просто текст
                value = ', '.join(a.get_text(strip=True) for a in value_span.find_all('a'))
                if not value:  # якщо посилань немає, беремо просто текст
                    value = value_span.get_text(strip=True)
                specifications[key] = value

    product['specifications'] = specifications

    return product


# ------------------ Збереження в БД (динамічно) ------------------

def save_to_db(product_data):
    """
    Зберігає дані продукту в БД.
    Якщо є продукт з таким же кодом і всі поля однакові — нічого не робимо.
    Якщо є продукт з таким же кодом, але дані змінились — оновлюємо.
    Якщо немає продукту з кодом — створюємо.
    """
    from django.db.models import Q

    # Список полів моделі (без PK, M2M)
    model_fields = [f for f in Product._meta.get_fields()
                    if getattr(f, 'concrete', False) and not getattr(f, 'auto_created', False)]
    field_names = {f.name: f for f in model_fields}

    save_kwargs = {}
    for field_name, field_obj in field_names.items():
        if field_obj.primary_key:
            continue
        value = product_data.get(field_name)
        if value is not None:
            save_kwargs[field_name] = value

    try:
        code = save_kwargs.get('code')
        if code:
            # шукаємо продукт по code
            obj = Product.objects.filter(code=code).first()
            if obj:
                # перевіряємо, чи всі поля збігаються
                duplicate = True
                for k, v in save_kwargs.items():
                    if getattr(obj, k) != v:
                        duplicate = False
                        break

                if duplicate:
                    print(f"[DB] Продукт (code={code}) вже існує — не створюємо дубліката")
                    return obj
                else:
                    # оновлюємо
                    for k, v in save_kwargs.items():
                        setattr(obj, k, v)
                    obj.save()
                    print(f"[DB] Оновлено Product (code={code}) id={obj.pk}")
                    return obj
            else:
                # створюємо новий
                obj = Product.objects.create(**save_kwargs)
                print(f"[DB] Створено Product (code={code}) id={obj.pk}")
                return obj
        else:
            # без коду просто створюємо новий
            obj = Product.objects.create(**save_kwargs)
            print(f"[DB] Створено Product id={obj.pk}")
            return obj

    except Exception as e:
        print(f"[ERROR] Помилка збереження в БД: {e}")
        return None




# ------------------ MAIN ------------------
if __name__ == "__main__":
    # Список URL для парсингу — заміни на реальні сторінки
    PRODUCT_URLS = [
        "https://brain.com.ua/ukr/Mobilniy_telefon_Apple_iPhone_16_Pro_Max_256GB_Black_Titanium-p1145443.html",
        "https://brain.com.ua/ukr/Mobilniy_telefon_Apple_iPhone_13_128GB_Midnight_MLPF3-p800204.html",
    ]

    for url in PRODUCT_URLS:
        print(f"\nПарсинг: {url}")
        try:
            data = parse_single_product(url)
            if not data:
                print("[WARN] Дані не отримані")
                continue

            # Вивід у консоль (гарно)
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))

            # Збереження у БД (через Django ORM)
            save_to_db(data)

            # Будь ласка, ввічливо — невелика пауза між запитами
            time.sleep(1.0)
        except Exception as e:
            print(f"[ERROR] Помилка при обробці {url}: {e}")
            continue

    print("\nГотово.")
