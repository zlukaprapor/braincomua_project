import time
import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin
import asyncio

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from asgiref.sync import sync_to_async

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


# ==================== HELPERS ====================

async def get_text_or_none(page, xpath):
    """Повертає текст елемента або None, якщо не знайдено"""
    try:
        element = page.locator(f"xpath={xpath}").first
        count = await element.count()
        if count > 0:
            text = await element.text_content()
            return text.strip() if text else None
        return None
    except Exception:
        return None


async def get_price_or_none(page, xpath):
    """Повертає число-ціну або None"""
    txt = await get_text_or_none(page, xpath)
    return _parse_price(txt) if txt else None


async def get_photos(page, url):
    """Збирає всі фото товару"""
    photos = []
    try:
        img_elements = await page.locator("xpath=//img[@class='zoomImg']").all()
        for img in img_elements:
            src = (await img.get_attribute('data-big-picture-src') or
                   await img.get_attribute('data-src') or
                   await img.get_attribute('src'))
            if src:
                src = src.strip()
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(url, src)
                elif not src.startswith('http'):
                    src = urljoin(url, src)
                photos.append(src)
    except Exception:
        pass
    return _unique_preserve_order(photos)


# ==================== PARSER ====================

async def parse_single_product(url, page, timeout=12000):
    """timeout в мілісекундах для Playwright"""
    product = {}

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=timeout)

        # Чекаємо на завантаження основного контенту
        await page.wait_for_selector("xpath=//h1", timeout=timeout)
        await asyncio.sleep(2)

        # Перехід до секції "Характеристики"
        try:
            char_link = page.locator("xpath=//a[@href='#br-characteristics']").first
            count = await char_link.count()
            if count > 0:
                await char_link.click()
                await asyncio.sleep(1)
        except Exception:
            pass

        # Розгортаємо всі характеристики
        try:
            show_all_button = page.locator("xpath=//button[@class='br-prs-button']").first
            count = await show_all_button.count()
            if count > 0:
                await show_all_button.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                await show_all_button.click()
                await asyncio.sleep(2)
        except Exception:
            pass

    except PlaywrightTimeoutError:
        print(f"[ERROR] Таймаут при завантаженні {url}")
        return None
    except Exception as e:
        print(f"[ERROR] Не вдалось завантажити {url}: {e}")
        return None

    product["link"] = url

    # ==================== Назва товару ====================
    product["title"] = await get_text_or_none(page, "//div[@id='br-pr-1']/h1")
    product["full_name"] = product["title"]

    # ==================== Основні характеристики (mapping) ====================
    field_map = {
        "color": "//div[@class='br-pr-chr-item']//div[./span[normalize-space(text())='Колір']]/span[2]",
        "memory": "//span[contains(text(), 'Вбудована пам')]/following-sibling::span[1]",
        "article": "//span[normalize-space(text())='Артикул']/following-sibling::span[1]",
        "diagonal": "//span[normalize-space(text())='Діагональ екрану']/following-sibling::span[1]",
        "resolution": "//span[normalize-space(text())='Роздільна здатність екрану']/following-sibling::span[1]",
    }

    for key, xpath in field_map.items():
        product[key] = await get_text_or_none(page, xpath)

    # ==================== Продавець ====================
    product["vendor"] = await get_text_or_none(page, "//div[@class='delivery-target']//strong")

    # ==================== Ціна ====================
    product["price"] = await get_price_or_none(page, "//div[@class='br-pr-np']//div/span[1]")

    # ==================== Акційна ціна ====================
    discount = await get_price_or_none(page, "//div[@class='br-pr-np-hz']//div/span[1]")
    product["discount_price"] = discount or product["price"]

    # ==================== Фото ====================
    product["photos"] = await get_photos(page, url)

    # ==================== Код товару ====================
    try:
        code_el = page.locator("xpath=//div[@id='product_code']//span[contains(@class,'br-pr-code-val')]").first
        count = await code_el.count()
        if count > 0:
            text = await code_el.text_content()
            product["code"] = text.strip() if text else None
        else:
            product["code"] = None
    except Exception:
        product["code"] = None

    # ==================== Кількість відгуків ====================
    try:
        reviews_el = page.locator("xpath=//a[@href='#reviews-list']/span").first
        count = await reviews_el.count()
        if count > 0:
            text = await reviews_el.text_content()
            product["reviews_count"] = int(text.strip()) if text else None
        else:
            product["reviews_count"] = None
    except (ValueError, Exception):
        product["reviews_count"] = None

    # ==================== Усі характеристики ====================
    specifications = {}
    try:
        char_blocks = await page.locator("xpath=//div[contains(@class, 'br-pr-chr-item')]").all()
        for block in char_blocks:
            rows = await block.locator("xpath=.//div/div").all()
            for row in rows:
                spans = await row.locator("xpath=.//span").all()
                if len(spans) >= 2:
                    key_text = await spans[0].text_content()
                    key = key_text.strip() if key_text else ""
                    if not key:
                        continue
                    links = await spans[1].locator("xpath=.//a").all()
                    if links:
                        values = []
                        for a in links:
                            link_text = await a.text_content()
                            if link_text and link_text.strip():
                                values.append(link_text.strip())
                        value = ", ".join(values)
                    else:
                        val_text = await spans[1].text_content()
                        value = val_text.strip() if val_text else ""
                    if value:
                        specifications[key] = value
    except Exception:
        pass

    product["specifications"] = specifications

    return product


# ------------------ Збереження в БД ------------------
@sync_to_async
def save_to_db(product_data):
    """Зберігає дані продукту в БД."""
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
async def main():
    PRODUCT_URLS = [
        "https://brain.com.ua/ukr/Mobilniy_telefon_Apple_iPhone_13_128GB_Starlight_MLPG3-p800206.html",
    ]

    async with async_playwright() as p:
        # Запуск браузера
        browser = await p.chromium.launch(
            headless=False,  # Змініть на True для headless режиму
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-gpu',
            ]
        )

        # Створення контексту з налаштуваннями
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0'
        )

        # Приховування автоматизації
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """)

        page = await context.new_page()

        try:
            for url in PRODUCT_URLS:
                print(f"\nПарсинг: {url}")
                try:
                    data = await parse_single_product(url, page)
                    if not data:
                        print("[WARN] Дані не отримані")
                        continue

                    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                    await save_to_db(data)
                    await asyncio.sleep(2.0)
                except Exception as e:
                    print(f"[ERROR] Помилка при обробці {url}: {e}")
                    continue
        finally:
            await context.close()
            await browser.close()

    print("\nГотово.")


if __name__ == "__main__":
    asyncio.run(main())