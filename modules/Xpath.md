# 📋 Інструкція з підбору XPath для парсингу

## ⚠️ ВАЖЛИВО!
**Всі XPath у скриптах - це тільки ПРИКЛАДИ! Ви ПОВИННІ підібрати свої XPath вручну для кожного елемента!**

---

## 🔍 Покрокова інструкція

### Крок 1: Відкрийте сторінку в браузері
1. Відкрийте Chrome/Firefox
2. Перейдіть на цільову сторінку товару
3. Натисніть **F12** або **Ctrl+Shift+I** (DevTools)

### Крок 2: Знайдіть потрібний елемент
1. Натисніть на іконку **Select Element** (стрілка в кутку DevTools) або **Ctrl+Shift+C**
2. Наведіть курсор на потрібний елемент на сторінці (назва, ціна, фото і т.д.)
3. Клікніть - елемент підсвітиться в коді

### Крок 3: Створіть XPath вручну
**НЕ КОПІЮЙТЕ** автоматично згенерований XPath! Створіть свій:

#### Приклади правильних XPath:

**Для назви товару:**
```xpath
//h1[@class="product-title"]
//div[@id="product-info"]//h1
//h1[contains(@class, "title")]
```

**Для ціни:**
```xpath
//span[@class="price-value"]
//div[contains(@class, "price-block")]//span
//span[@data-price-type="current"]
```

**Для характеристики "Колір":**
```xpath
//span[text()='Колір']/following-sibling::span[1]
//div[@class="specs"]//span[contains(text(), 'Колір')]/../span[2]
```

**Для всіх фото:**
```xpath
//img[@class="product-image"]
//div[@class="gallery"]//img
//img[contains(@data-src, 'product')]
```

**Для характеристик (список):**
```xpath
//div[@class="specifications"]//div[@class="spec-row"]
//table[@class="specs"]//tr
//ul[@class="features"]//li
```

### Крок 4: Перевірте XPath в Console
1. Відкрийте вкладку **Console** в DevTools
2. Введіть команду перевірки:
```javascript
$x("ваш_xpath_тут")
```

**Приклад:**
```javascript
$x("//h1[@class='product-title']")
```

3. Якщо XPath правильний - побачите масив з елементом(ами)
4. Якщо пустий масив `[]` - XPath неправильний, пробуйте інший

### Крок 5: Переконайтесь що знайдено ОДИН елемент
```javascript
$x("//h1[@class='product-title']").length
// Має повернути: 1
```

Якщо повертає більше 1 - зробіть XPath більш специфічним!

---

## 🎯 Типи XPath селекторів

### По атрибуту class
```xpath
//div[@class="product-name"]
//span[@class="price-value"]
```

### По атрибуту id
```xpath
//div[@id="product-code"]
//span[@id="price"]
```

### По тексту
```xpath
//span[text()='Колір']
//a[text()='Характеристики']
```

### По частковому текcту
```xpath
//span[contains(text(), 'Вбудована')]
//div[contains(text(), 'пам')]
```

### По частковому класу
```xpath
//div[contains(@class, 'product')]
//span[contains(@class, 'price')]
```

### Наступний сусідній елемент
```xpath
//span[text()='Колір']/following-sibling::span[1]
//label[text()='Пам'ять']/following-sibling::div
```

### Батьківський елемент
```xpath
//span[@class="value"]/../..
//div[@class="price"]/parent::div
```

### Відносний XPath (всередині елемента)
```xpath
.//span[@class="name"]
.//div[@class="value"]
```

---

## ✅ Чеклист перевірки XPath

- [ ] XPath знаходить **тільки 1 елемент** (якщо це не список)
- [ ] XPath **не занадто довгий** (уникайте: `/html/body/div[1]/div[2]/...`)
- [ ] XPath **не занадто короткий** (уникайте: `//span` без уточнень)
- [ ] XPath **працює** в Console (`$x("xpath")`)
- [ ] XPath **стабільний** (не залежить від випадкових класів типу `jsx-123456`)
- [ ] Для **списків** XPath знаходить **всі потрібні елементи**

---

## 🚫 Типові помилки

### ❌ Копіювання автоматичного XPath
```xpath
// НЕ РОБІТЬ ТАК:
/html/body/div[1]/div[3]/div[1]/div[2]/div[1]/main/div[1]/div[1]/div[1]/div[1]/div[1]/h1
```

### ✅ Правильний підхід
```xpath
// РОБІТЬ ТАК:
//h1[@class="product-title"]
або
//div[@id="product"]//h1
```

### ❌ Занадто загальний XPath
```xpath
//span  // Знайде ВСІ span на сторінці!
```

### ✅ Специфічний XPath
```xpath
//div[@class="price-block"]//span[@class="amount"]
```

---

## 📝 Приклад роботи з одним елементом

### Завдання: знайти назву товару

1. **Знаходимо елемент на сторінці** (F12 + Select Element)
2. **Дивимось структуру HTML:**
```html
<div class="product-header">
  <h1 class="product-name">iPhone 16 Pro Max</h1>
</div>
```

3. **Створюємо XPath варіанти:**
```xpath
Варіант 1: //h1[@class="product-name"]
Варіант 2: //div[@class="product-header"]//h1
Варіант 3: //h1[contains(@class, "product-name")]
```

4. **Перевіряємо в Console:**
```javascript
$x("//h1[@class='product-name']")
// Результат: [h1.product-name]
```

5. **Використовуємо в коді:**
```python
# Selenium
title_element = driver.find_element(By.XPATH, "//h1[@class='product-name']")

# Playwright
title_element = page.locator("xpath=//h1[@class='product-name']").first
```

---

## 🎓 Корисні ресурси

- [XPath Cheatsheet](https://devhints.io/xpath)
- [XPath Tutorial (W3Schools)](https://www.w3schools.com/xml/xpath_intro.asp)
- Використовуйте плагіни для браузера: **ChroPath**, **XPath Helper**

---

## 💡 Поради для ефективного парсингу

1. **Починайте з простих XPath** - ускладнюйте тільки якщо потрібно
2. **Уникайте індексів** типу `[1]`, `[2]` де можливо - вони можуть змінюватись
3. **Використовуйте `contains()`** для гнучкості
4. **Перевіряйте XPath на різних товарах** - переконайтесь що працює універсально
5. **Зберігайте список робочих XPath** в окремому файлі для зручності

---

## 🔄 Що робити якщо XPath не працює?

1. Перевірте чи завантажився елемент (динамічний контент)
2. Додайте очікування завантаження (`WebDriverWait`, `page.wait_for_selector`)
3. Перевірте чи правильно екрановані лапки
4. Спробуйте альтернативний XPath
5. Перевірте чи елемент всередині iframe
6. Подивіться чи не змінюється структура сторінки

---

**Успішного парсингу! 🚀**