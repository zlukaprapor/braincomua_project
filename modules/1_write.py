"""
1_write.py
Створює TestItem у базі даних.
"""
from load_django import *
from parser_app.models import TestItem

item = TestItem.objects.create(name='script_write', value=123)
print(f'Created: id={item.id} name={item.name} value={item.value}')