import time
import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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


# ------------------ Selenium Driver Setup ------------------
def create_driver():
    """Створює та налаштовує Selenium WebDriver."""
    chrome_options = Options()

    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0')

    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # Для headless режиму:
    # chrome_options.add_argument('--headless')

    driver = webdriver.Chrome(options=chrome_options)

    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        '''
    })

    return driver


# ------------------ PARSER ------------------
def parse_single_product(url, driver, timeout=12):

    product = {}

    try:
        driver.get(url)

        # Чекаємо на завантаження основного контенту
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, "//h1"))
        )

        time.sleep(2)

        # ============ ПЕРЕХОДИМО ДО СЕКЦІЇ ХАРАКТЕРИСТИК ============
        try:
            # Знаходимо посилання "Характеристики"
            char_link = driver.find_element(By.XPATH, "//a[@href='#br-characteristics']")
            driver.execute_script("arguments[0].click();", char_link)
            time.sleep(1)
        except Exception as e:
            print(f"[WARN] Не вдалось перейти до характеристик: {e}")

        # ============ РОЗГОРТАЄМО ВСІ ХАРАКТЕРИСТИКИ ============
        try:
            show_all_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "br-prs-button"))
            )

            # Прокручуємо до кнопки
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_all_button)
            time.sleep(0.5)

            # Натискаємо через JavaScript (надійніше)
            driver.execute_script("arguments[0].click();", show_all_button)
            time.sleep(2)  # Збільшена пауза для завантаження

        except TimeoutException:
            print("[WARN] Кнопка 'Всі характеристики' не знайдена")
        except Exception as e:
            print(f"[WARN] Помилка при розгортанні: {e}")

    except TimeoutException as e:
        print(f"[ERROR] Таймаут при завантаженні {url}: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Не вдалось завантажити {url}: {e}")
        return None

    product['link'] = url

    # ==================== Назва товару ====================
    title = None
    try:
        title_element = driver.find_element(By.XPATH, "//div[@id='br-pr-1']/h1")  # ⚠️
        title = title_element.text.strip()
    except NoSuchElementException:
        print("[WARN] Не знайдено назву товару")

    product['title'] = title
    product['full_name'] = title

    # ==================== Колір ====================
    color = None
    try:
        color_element = driver.find_element(
            By.XPATH,
            "//div[@class='br-pr-chr-item']//div[./span[normalize-space(text())='Колір']]/span[2]"  # ⚠️
        )
        color = color_element.text.strip()
    except NoSuchElementException:
        print("[WARN] Не знайдено колір")
    product['color'] = color

    # ==================== Об'єм пам'яті ====================
    memory = None
    try:
        memory_element = driver.find_element(
            By.XPATH,
            "//span[contains(text(), 'Вбудована пам')]/following-sibling::span[1]"  # ⚠️
        )
        memory = memory_element.text.strip()
    except NoSuchElementException:
        print("[WARN] Не знайдено пам'ять")
    product['memory'] = memory

    # ==================== Продавець ====================
    vendor = None
    try:
        vendor_element = driver.find_element(
            By.XPATH,
            "//div[@class='delivery-target']//strong"  # ⚠️
        )
        vendor = vendor_element.text.strip()
    except NoSuchElementException:
        print("[WARN] Не знайдено продавця")
    product['vendor'] = vendor

    # ==================== Ціна ====================
    price = None
    try:
        price_element = driver.find_element(
            By.XPATH,
            "//div[@class='br-pr-np']//div/span[1]"  # ⚠️
        )
        price = _parse_price(price_element.text)
    except NoSuchElementException:
        print("[WARN] Не знайдено ціну")
    product['price'] = price

    # ==================== Акційна ціна ====================
    discount_price = None
    try:
        discount_element = driver.find_element(
            By.XPATH,
            "//div[@class='br-pr-np-hz']//div/span[1]"  # ⚠️
        )
        discount_price = _parse_price(discount_element.text)
    except NoSuchElementException:
        discount_price = price
    product['discount_price'] = discount_price

    # ==================== Всі фото товару ====================
    photos = []
    try:
        img_elements = driver.find_elements(
            By.XPATH,
            "//img[@class='zoomImg']"  # ⚠️
        )
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
    code = None
    try:
        code_element = driver.find_element(
            By.XPATH,
            "//div[@id='product_code']//span[contains(@class,'br-pr-code-val')]"
        )
        code = code_element.get_attribute("textContent").strip()
    except NoSuchElementException:
        print("[WARN] Не знайдено код товару")
    product['code'] = code

    # ==================== Кількість відгуків ====================
    reviews_count = 0
    try:
        reviews_element = driver.find_element(
            By.XPATH,
            "//a[@href='#reviews-list']/span"  # ⚠️
        )
        reviews_count = int(reviews_element.text.strip())
    except (NoSuchElementException, ValueError):
        pass
    product['reviews_count'] = reviews_count

    # ==================== Артикул ====================
    article = None
    try:
        article_element = driver.find_element(
            By.XPATH,
            "//span[normalize-space(text())='Артикул']/following-sibling::span[1]"  # ⚠️
        )
        article = article_element.text.strip()
    except NoSuchElementException:
        print("[WARN] Не знайдено артикул")
    product['article'] = article

    # ==================== Діагональ екрану ====================
    diagonal = None
    try:
        diagonal_element = driver.find_element(
            By.XPATH,
            "//span[normalize-space(text())='Діагональ екрану']/following-sibling::span[1]"  # ⚠️
        )
        diagonal = diagonal_element.text.strip()
    except NoSuchElementException:
        print("[WARN] Не знайдено діагональ")
    product['diagonal'] = diagonal

    # ==================== Роздільна здатність ====================
    resolution = None
    try:
        resolution_element = driver.find_element(
            By.XPATH,
            "//span[normalize-space(text())='Роздільна здатність екрану']/following-sibling::span[1]"  # ⚠️
        )
        resolution = resolution_element.text.strip()
    except NoSuchElementException:
        print("[WARN] Не знайдено роздільну здатність")
    product['resolution'] = resolution

    # ==================== Всі характеристики ====================
    specifications = {}
    try:

        # Знаходимо всі блоки з характеристиками
        char_blocks = driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'br-pr-chr-item')]"
        )

        for block in char_blocks:
            try:
                # В кожному блоці шукаємо всі пари ключ-значення
                rows = block.find_elements(By.XPATH, ".//div/div")

                for row in rows:
                    try:
                        spans = row.find_elements(By.XPATH, ".//span")

                        if len(spans) >= 2:
                            key = spans[0].text.strip()

                            # Перевіряємо чи є посилання в значенні
                            links = spans[1].find_elements(By.TAG_NAME, "a")
                            if links:
                                value = ", ".join(a.text.strip() for a in links if a.text.strip())
                            else:
                                value = spans[1].text.strip()

                            if key and value:
                                specifications[key] = value

                    except (NoSuchElementException, IndexError):
                        continue

            except Exception as e:
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
        "https://brain.com.ua/ukr/Mobilniy_telefon_Apple_iPhone_15_128GB_Black-p1044347.html",
    ]

    driver = create_driver()

    try:
        for url in PRODUCT_URLS:
            print(f"\nПарсинг: {url}")
            try:
                data = parse_single_product(url, driver)
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
        driver.quit()

    print("\nГотово.")