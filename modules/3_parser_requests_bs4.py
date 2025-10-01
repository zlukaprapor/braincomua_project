import time
import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from django.db.models import Q
from load_django import *
from parser_app.models import Product

# ------------------ HTTP заголовки для requests ------------------
# Імітуємо браузер, щоб сайт не блокував запити
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
    'TE': 'Trailers',
}


# ------------------ Утиліти ------------------
def _parse_price(text):
    """
    Витягує числове значення з рядка та перетворює його у Decimal.
    Повертає None, якщо перетворення неможливе.
    """
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
    """
    Повертає список без дублікатів, зберігаючи порядок.
    """
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ------------------ Основний парсер ------------------
def parse_single_product(url, headers=HEADERS, timeout=12):
    """
    Парсить сторінку товару Brain.com.ua та повертає словник з даними.
    """
    product = {}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Не вдалось завантажити {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Посилання на джерело
    product['link'] = url

    # Назва товару
    try:
        title = soup.select_one("h1") or soup.select_one(".product-title")
        product["title"] = title.get_text(strip=True) if title else None
        product["full_name"] = product["title"]
    except AttributeError:
        product["title"] = None
        product["full_name"] = None

    # Характеристики як словник (ключ → значення)
    characteristics = {}
    try:
        for span in soup.select(".br-pr-chr-item span"):
            try:
                next_span = span.find_next_sibling("span")
                if next_span:
                    key = span.get_text(strip=True)
                    value = next_span.get_text(strip=True)
                    characteristics[key] = value
            except AttributeError:
                continue
    except Exception:
        characteristics = {}

    # Основні параметри товару
    product["color"] = characteristics.get("Колір") or characteristics.get("Цвет")
    product["memory"] = characteristics.get("Вбудована пам'ять") or characteristics.get("Встроенная память")
    product["article"] = characteristics.get("Артикул")
    product["diagonal"] = characteristics.get("Діагональ екрану") or characteristics.get("Диагональ экрана")
    product["resolution"] = characteristics.get("Роздільна здатність екрану") or characteristics.get(
        "Разрешение дисплея")

    # Продавець
    v_sel = soup.select_one(".br-pr-del-type .delivery-target strong")
    product["vendor"] = v_sel.get_text(strip=True) if v_sel else None

    # Ціна
    p_sel = soup.select_one(".br-pr-price.main-price-block .br-pr-np > div > span")
    product["price"] = _parse_price(p_sel.get_text(strip=True)) if p_sel else None

    # Акційна ціна (якщо є)
    d_sel = soup.select_one(".br-pr-price.main-price-block .br-pr-np-hz > div > span")
    discount_price = _parse_price(d_sel.get_text(strip=True)) if d_sel else None
    product["discount_price"] = discount_price if discount_price else product["price"]

    # Фото
    photos = []
    for img in soup.select("img.dots-image"):
        src = img.get("data-big-picture-src") or img.get("src")
        if src:
            src = src.strip()
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(url, src)
            elif not src.startswith("http"):
                src = urljoin(url, src)
            photos.append(src)
    product["photos"] = _unique_preserve_order(photos)

    # Код товару
    code_sel = soup.select_one("#product_code .br-pr-code-val")
    product["code"] = code_sel.get_text(strip=True) if code_sel else None

    # Кількість відгуків
    try:
        rev_sel = soup.select_one("a.scroll-to-element span")
        product["reviews_count"] = int(rev_sel.get_text(strip=True)) if rev_sel else None
    except (AttributeError, ValueError):
        product["reviews_count"] = None

    # Усі характеристики (словник)
    specifications = {}
    try:
        for item in soup.select(".br-pr-chr-item"):
            for row in item.select("div > div"):
                key_span = row.find("span")
                value_span = key_span.find_next_sibling("span") if key_span else None
                if key_span and value_span:
                    key = key_span.get_text(strip=True)
                    value = ", ".join(a.get_text(strip=True) for a in value_span.find_all("a"))
                    if not value:
                        value = value_span.get_text(strip=True)
                    specifications[key] = value
    except Exception:
        specifications = {}
    product["specifications"] = specifications

    return product


# ------------------ Збереження в БД ------------------
def save_to_db(product_data):
    """
    Зберігає дані продукту в БД через Django ORM.
    Логіка:
    - Якщо продукт з таким кодом існує і дані не змінились → нічого не робимо.
    - Якщо продукт з таким кодом існує, але дані змінились → оновлюємо.
    - Якщо продукту з таким кодом немає → створюємо новий.
    """

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
            obj = Product.objects.filter(code=code).first()
            if obj:
                # Якщо всі поля збігаються → нічого не робимо
                duplicate = all(getattr(obj, k) == v for k, v in save_kwargs.items())
                if duplicate:
                    print(f"[DB] Продукт (code={code}) вже існує — не створюємо дубліката")
                    return obj
                else:
                    # Оновлюємо поля
                    for k, v in save_kwargs.items():
                        setattr(obj, k, v)
                    obj.save()
                    print(f"[DB] Оновлено Product (code={code}) id={obj.pk}")
                    return obj
            else:
                # Новий продукт
                obj = Product.objects.create(**save_kwargs)
                print(f"[DB] Створено Product (code={code}) id={obj.pk}")
                return obj
        else:
            # Якщо немає коду, створюємо без нього
            obj = Product.objects.create(**save_kwargs)
            print(f"[DB] Створено Product id={obj.pk}")
            return obj

    except Exception as e:
        print(f"[ERROR] Помилка збереження в БД: {e}")
        return None


# ------------------ MAIN ------------------
if __name__ == "__main__":
    PRODUCT_URLS = [
        "https://brain.com.ua/ukr/Mobilniy_telefon_Apple_iPhone_16_Pro_Max_256GB_Black_Titanium-p1145443.html",
    ]

    for url in PRODUCT_URLS:
        print(f"\nПарсинг: {url}")
        try:
            data = parse_single_product(url)
            if not data:
                print("[WARN] Дані не отримані")
                continue

            # Вивід у консоль
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))

            # Збереження у БД
            save_to_db(data)

            # Невелика пауза, щоб не перевантажувати сайт
            time.sleep(1.0)
        except Exception as e:
            print(f"[ERROR] Помилка при обробці {url}: {e}")
            continue

    print("\nГотово.")
