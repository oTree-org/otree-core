"""oTree Public API utilities"""

from easymoney import Money as Currency
from django.utils.safestring import mark_safe
import json

def safe_json(obj):
    return mark_safe(json.dumps(obj))

def currency_range(first, last, increment=Currency(0.01)):
    assert last >= first
    assert increment >= 0
    values = []
    current_value = Currency(first)
    while True:
        if current_value > last:
            return values
        values.append(current_value)
        current_value += increment
