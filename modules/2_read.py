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