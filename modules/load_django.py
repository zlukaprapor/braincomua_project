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