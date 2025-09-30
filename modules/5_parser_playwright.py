import time
import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from load_django import *
from parser_app.models import Product


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
def parse_single_product(page, url, timeout=12000):
    """
    Парсить одну сторінку товару за допомогою Playwright з XPath селекторами.
    timeout у мілісекундах (12000 = 12 секунд)

    ⚠️ ВАЖЛИВО: Всі XPath нижче - це ПРИКЛАДИ!
    Ви ПОВИННІ підібрати свої XPath вручну через інспектор браузера:
    1. Відкрийте сторінку в Chrome
    2. F12 -> Elements
    3. Ctrl+F для пошуку XPath
    4. Перевірте XPath командою $x("ваш_xpath") в Console
    5. Переконайтесь що XPath знаходить ОДИН правильний елемент
    """
    product = {}

    try:
        page.goto(url, wait_until='domcontentloaded', timeout=timeout)
        page.wait_for_selector('xpath=//h1', timeout=timeout)
        time.sleep(2)
    except PlaywrightTimeout as e:
        print(f"[ERROR] Таймаут при завантаженні {url}: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Не вдалось завантажити {url}: {e}")
        return None

    product['link'] = url

    # ==================== Назва товару ====================
    # ПРИКЛАД XPath (замініть на свій!):
    # xpath=//h1[@class="product-name"]
    # xpath=//div[@class="product-header"]//h1
    # xpath=//h1[contains(@class, "title")]
    title = None
    try:
        title_element = page.locator('xpath=//h1').first  # ⚠️ ЗАМІНІТЬ НА СВІЙ XPATH!
        title = title_element.text_content().strip()
    except Exception:
        print("[WARN] Не знайдено назву товару")

    product['title'] = title
    product['full_name'] = title

    # ==================== Колір ====================
    # ПРИКЛАД XPath для пошуку характеристики "Колір":
    # xpath=//span[text()='Колір']/following-sibling::span[1]
    # xpath=//div[contains(@class, 'characteristic')]//span[contains(text(), 'Колір')]/following-sibling::span
    color = None
    try:
        color_element = page.locator(
            "xpath=//span[text()='Колір']/following-sibling::span[1]"  # ⚠️ ЗАМІНІТЬ!
        ).first
        color = color_element.text_content().strip()
    except Exception:
        print("[WARN] Не знайдено колір")
    product['color'] = color

    # ==================== Об'єм пам'яті ====================
    # ПРИКЛАД XPath:
    # xpath=//span[contains(text(), 'Вбудована пам')]/following-sibling::span[1]
    memory = None
    try:
        memory_element = page.locator(
            "xpath=//span[contains(text(), 'Вбудована пам')]/following-sibling::span[1]"  # ⚠️ ЗАМІНІТЬ!
        ).first
        memory = memory_element.text_content().strip()
    except Exception:
        print("[WARN] Не знайдено пам'ять")
    product['memory'] = memory

    # ==================== Продавець ====================
    # ПРИКЛАД XPath:
    # xpath=//div[@class='vendor-info']//strong
    # xpath=//div[contains(@class, 'delivery')]//strong
    vendor = None
    try:
        vendor_element = page.locator(
            "xpath=//div[@class='delivery-target']//strong"  # ⚠️ ЗАМІНІТЬ!
        ).first
        vendor = vendor_element.text_content().strip()
    except Exception:
        print("[WARN] Не знайдено продавця")
    product['vendor'] = vendor

    # ==================== Ціна ====================
    # ПРИКЛАД XPath:
    # xpath=//span[@class='price-value']
    # xpath=//div[contains(@class, 'price')]//span[@class='amount']
    price = None
    try:
        price_element = page.locator(
            "xpath=//div[@class='main-price-block']//span[@class='price-value']"  # ⚠️ ЗАМІНІТЬ!
        ).first
        price = _parse_price(price_element.text_content())
    except Exception:
        print("[WARN] Не знайдено ціну")
    product['price'] = price

    # ==================== Акційна ціна ====================
    # ПРИКЛАД XPath:
    # xpath=//span[@class='discount-price']
    # xpath=//div[contains(@class, 'special-price')]//span
    discount_price = None
    try:
        discount_element = page.locator(
            "xpath=//div[@class='discount-price-block']//span[@class='price-value']"  # ⚠️ ЗАМІНІТЬ!
        ).first
        discount_price = _parse_price(discount_element.text_content())
    except Exception:
        discount_price = price
    product['discount_price'] = discount_price

    # ==================== Всі фото товару ====================
    # ПРИКЛАД XPath:
    # xpath=//img[@class='product-image']
    # xpath=//div[@class='gallery']//img
    # xpath=//img[contains(@class, 'product-photo')]
    photos = []
    try:
        img_elements = page.locator(
            "xpath=//img[@class='product-gallery-image']"  # ⚠️ ЗАМІНІТЬ!
        ).all()

        for img in img_elements:
            # Спробуйте різні атрибути: data-src, data-large, src
            src = img.get_attribute('data-big-picture-src') or \
                  img.get_attribute('data-src') or \
                  img.get_attribute('src')
            if src:
                src = src.strip()
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(url, src)
                elif not src.startswith('http'):
                    src = urljoin(url, src)
                photos.append(src)
    except Exception as e:
        print(f"[WARN] Помилка збору фото: {e}")

    product['photos'] = _unique_preserve_order(photos)

    # ==================== Код товару ====================
    # ПРИКЛАД XPath:
    # xpath=//span[@class='product-code']
    # xpath=//div[contains(text(), 'Код')]/following-sibling::span
    code = None
    try:
        code_element = page.locator(
            "xpath=//span[@class='product-code-value']"  # ⚠️ ЗАМІНІТЬ!
        ).first
        code = code_element.text_content().strip()
    except Exception:
        print("[WARN] Не знайдено код товару")
    product['code'] = code

    # ==================== Кількість відгуків ====================
    # ПРИКЛАД XPath:
    # xpath=//span[@class='reviews-count']
    # xpath=//a[contains(@href, 'reviews')]//span
    reviews_count = 0
    try:
        reviews_element = page.locator(
            "xpath=//a[contains(@class, 'reviews-link')]//span"  # ⚠️ ЗАМІНІТЬ!
        ).first
        reviews_count = int(reviews_element.text_content().strip())
    except (Exception, ValueError):
        pass
    product['reviews_count'] = reviews_count

    # ==================== Артикул ====================
    # ПРИКЛАД XPath:
    # xpath=//span[text()='Артикул']/following-sibling::span[1]
    article = None
    try:
        article_element = page.locator(
            "xpath=//span[text()='Артикул']/following-sibling::span[1]"  # ⚠️ ЗАМІНІТЬ!
        ).first
        article = article_element.text_content().strip()
    except Exception:
        print("[WARN] Не знайдено артикул")
    product['article'] = article

    # ==================== Діагональ екрану ====================
    # ПРИКЛАД XPath:
    # xpath=//span[contains(text(), 'Діагональ')]/following-sibling::span[1]
    diagonal = None
    try:
        diagonal_element = page.locator(
            "xpath=//span[contains(text(), 'Діагональ')]/following-sibling::span[1]"  # ⚠️ ЗАМІНІТЬ!
        ).first
        diagonal = diagonal_element.text_content().strip()
    except Exception:
        print("[WARN] Не знайдено діагональ")
    product['diagonal'] = diagonal

    # ==================== Роздільна здатність ====================
    # ПРИКЛАД XPath:
    # xpath=//span[contains(text(), 'Роздільна')]/following-sibling::span[1]
    resolution = None
    try:
        resolution_element = page.locator(
            "xpath=//span[contains(text(), 'Роздільна')]/following-sibling::span[1]"  # ⚠️ ЗАМІНІТЬ!
        ).first
        resolution = resolution_element.text_content().strip()
    except Exception:
        print("[WARN] Не знайдено роздільну здатність")
    product['resolution'] = resolution

    # ==================== Всі характеристики ====================
    # ПРИКЛАД XPath для всіх характеристик:
    # xpath=//div[@class='characteristics']//div[@class='char-row']
    # xpath=//table[@class='specs']//tr
    specifications = {}
    try:
        # Знаходимо всі рядки характеристик
        char_rows = page.locator(
            "xpath=//div[@class='characteristics-list']//div[@class='char-item']"  # ⚠️ ЗАМІНІТЬ!
        ).all()

        for row in char_rows:
            try:
                # XPath для назви характеристики (відносно row)
                # В Playwright для відносного XPath використовуємо locator всередині row
                key = row.locator("xpath=.//span[@class='char-name']").first.text_content().strip()  # ⚠️ ЗАМІНІТЬ!
                # XPath для значення характеристики (відносно row)
                value = row.locator("xpath=.//span[@class='char-value']").first.text_content().strip()  # ⚠️ ЗАМІНІТЬ!

                if key and value:
                    specifications[key] = value
            except Exception:
                continue
    except Exception as e:
        print(f"[WARN] Помилка збору характеристик: {e}")

    product['specifications'] = specifications

    return product


# ------------------ Збереження в БД ------------------
def save_to_db(product_data):
    """Зберігає дані продукту в БД."""
    from django.db.models import Q

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
                duplicate = True
                for k, v in save_kwargs.items():
                    if getattr(obj, k) != v:
                        duplicate = False
                        break

                if duplicate:
                    print(f"[DB] Продукт (code={code}) вже існує — не створюємо дубліката")
                    return obj
                else:
                    for k, v in save_kwargs.items():
                        setattr(obj, k, v)
                    obj.save()
                    print(f"[DB] Оновлено Product (code={code}) id={obj.pk}")
                    return obj
            else:
                obj = Product.objects.create(**save_kwargs)
                print(f"[DB] Створено Product (code={code}) id={obj.pk}")
                return obj
        else:
            obj = Product.objects.create(**save_kwargs)
            print(f"[DB] Створено Product id={obj.pk}")
            return obj

    except Exception as e:
        print(f"[ERROR] Помилка збереження в БД: {e}")
        return None


# ------------------ MAIN ------------------
if __name__ == "__main__":
    # ⚠️ ВАЖЛИВЕ НАГАДУВАННЯ:
    # Перед запуском скрипта ОБОВ'ЯЗКОВО підберіть всі XPath вручну!
    # Використовуйте інспектор браузера та перевіряйте в Console: $x("ваш_xpath")

    PRODUCT_URLS = [
        "https://brain.com.ua/ukr/Mobilniy_telefon_Apple_iPhone_16_Pro_Max_256GB_Black_Titanium-p1145443.html",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # True для headless режиму
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-gpu',
            ]
        )

        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0',
            locale='uk-UA',
            timezone_id='Europe/Kiev'
        )

        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """)

        try:
            for url in PRODUCT_URLS:
                print(f"\nПарсинг: {url}")
                try:
                    data = parse_single_product(page, url)
                    if not data:
                        print("[WARN] Дані не отримані")
                        continue

                    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                    save_to_db(data)
                    time.sleep(2.0)
                except Exception as e:
                    print(f"[ERROR] Помилка при обробці {url}: {e}")
                    continue
        finally:
            context.close()
            browser.close()

    print("\nГотово.")