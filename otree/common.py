"""oTree Public API utilities"""

import json
from decimal import Decimal

from django.conf import settings
from django.utils.safestring import mark_safe

import easymoney


class Money(easymoney.Money):
    '''payment currency'''

    CODE = settings.PAYMENT_CURRENCY_CODE
    FORMAT = settings.PAYMENT_CURRENCY_FORMAT
    LOCALE = settings.PAYMENT_CURRENCY_LOCALE
    DECIMAL_PLACES = settings.PAYMENT_CURRENCY_DECIMAL_PLACES

    def to_number(self):
        return Decimal(self)

class Currency(easymoney.Money):
    '''game currency'''

    CODE = settings.GAME_CURRENCY_CODE
    FORMAT = settings.GAME_CURRENCY_FORMAT
    LOCALE = settings.GAME_CURRENCY_LOCALE
    DECIMAL_PLACES = settings.GAME_CURRENCY_DECIMAL_PLACES

    def to_money(self, subsession):
        # subsession arg can actually be a session as well
        # can't use isinstance() to avoid circular import
        if subsession.__class__.__name__ == 'Session':
            session = subsession
        else:
            session = subsession.session

        if settings.USE_POINTS:
            return Money(self * session.money_per_point)
        else:
            # should i convert to Money?
            return self

    def to_number(self):
        return Decimal(self)


class _CurrencyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, easymoney.Money):
            return float(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


def safe_json(obj):
    return mark_safe(json.dumps(obj, cls=_CurrencyEncoder))


# FIXME: there is a problem with currency = 0.01. this increment is too small
# if you use points. causes the function to hang.
def currency_range(first, last, increment):
    assert last >= first
    assert increment >= 0
    values = []
    current_value = Currency(first)
    while True:
        if current_value > last:
            return values
        values.append(current_value)
        current_value += increment
