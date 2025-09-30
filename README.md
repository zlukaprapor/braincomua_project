# Шаблон швидкого створення проекту для парсера (Windows)

## Передумови
* Python 3.9+ 
* pip
* PostgreSQL 
---

## Іменування

* Головна папка проєкту: `<domain>_project` (без точок), наприклад `fbraincomua_project`.
* Назва Django-проєкту: `<project_name>` (замість `braincomua` у прикладах).
* Базовий додаток завжди: `parser_app`.
* Папка для скриптів: `modules/`.

---

## Структура кінцевого проєкту (приклад)

braincomua_project/             # ім'я каталогу (замініть за потребою)
├── manage.py
├── braincomua/                 # django project (налаштування)
│   ├── settings.py
│   └── ...
├── parser_app/                 # django app
│   ├── models.py
│   └── ...
├── modules/                    #  скрипти
│   ├── __init__.py
│   ├── load_django.py
│   ├── 1_write.py
│   └── 2_read.py
├── results/
├── json/
└── files/

### 1)

python -m pip install --upgrade pip
pip install django psycopg2-binary

> `psycopg2-binary` — простий варіант для розробки. Для production краще ставити `psycopg2`.

### 2) Ініціалізація Django-проєкту + додатку

django-admin startproject braincomua .
python manage.py startapp parser_app

Відкрийте `myproject/settings.py` і додайте `parser_app` в `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    'parser_app',
]
```

### 3) Налаштування PostgreSQL

Через **pgAdmin** або `psql` створіть базу та користувача:

```sql
CREATE DATABASE parser_db;
CREATE USER parser_user WITH PASSWORD 'changeme';
GRANT ALL PRIVILEGES ON DATABASE parser_db TO parser_user;
```
```sql
GRANT ALL PRIVILEGES ON DATABASE parser_db TO parser_user;
GRANT ALL ON SCHEMA public TO parser_user;
ALTER SCHEMA public OWNER TO parser_user;
```

### 4) Налаштування `settings.py` для PostgreSQL

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'parser_db',
        'USER': 'parser_user',
        'PASSWORD': '12345678',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 5) Створення моделі в `parser_app/models.py`

```python
from django.db import models

class TestItem(models.Model):
    name = models.CharField(max_length=255)
    value = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.id} - {self.name}"
```

### 6) Міграції

python manage.py makemigrations parser_app
python manage.py migrate


### 7) Створити папку `modules` та файл `load_django.py`

```powershell
mkdir modules
ni modules\__init__.py -ItemType File
```
modules/load_django.py`:

```python
"""
load_django.py
Файл підключає Django з директорії проєкту. Розмістіть цей файл в modules/.
ПЕРЕЗАМІНІТЬ 'braincomua' на назву вашого django project package.
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'braincomua.settings')

import django
django.setup()
```

### 8) Тестові скрипти у `modules/`
1. `1_write.py` — записує запис у модель;
2. `2_read.py` — читає записи та виводить їх у `print()`.

`modules/1_write.py`:

```python
"""
1_write.py
Створює TestItem у базі даних.
"""
from load_django import *
from parser_app.models import TestItem

item = TestItem.objects.create(name='script_write', value=123)
print(f'Created: id={item.id} name={item.name} value={item.value}')
```

`modules/2_read.py`:

```python
"""
2_read.py
Зчитує всі TestItem та друкує їх у консоль.
"""
from load_django import *
from parser_app.models import TestItem

qs = TestItem.objects.all()
print('Found', qs.count(), 'items')
for it in qs:
    print(it.id, it.name, it.value, it.created_at)
```

Запуск:

```powershell
python modules/1_write.py
python modules/2_read.py
```


