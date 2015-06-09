"""oTree Public API utilities"""

import json
from decimal import Decimal

from django.conf import settings
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext

import easymoney


class RealWorldCurrency(easymoney.Money):
    '''payment currency'''

    CODE = settings.REAL_WORLD_CURRENCY_CODE
    LOCALE = settings.REAL_WORLD_CURRENCY_LOCALE
    DECIMAL_PLACES = settings.REAL_WORLD_CURRENCY_DECIMAL_PLACES

    def to_number(self):
        return Decimal(self)


class Currency(RealWorldCurrency):
    '''game currency'''

    if settings.USE_POINTS:
        # TODO: make this customizable?
        DECIMAL_PLACES = 0

    @classmethod
    def _format_currency(cls, number):
        if settings.USE_POINTS:
            # Translators: Show a number of points, e.g. "5 points"
            return ugettext('{} points').format(number)
        return super(Currency, cls)._format_currency(number)

    def to_real_world_currency(self, session):

        if settings.USE_POINTS:
            return RealWorldCurrency(
                self.to_number() * session.real_world_currency_per_point
            )
        else:
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
