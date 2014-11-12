"""oTree Public API utilities"""

from easymoney import Money, stdout_encode, _sanitize
from django.utils.safestring import mark_safe
import json
import otree.common_internal
from django.conf import settings
from decimal import Decimal
import otree.session.models

from easymoney import Money, MoneyField

class Currency(Money):

    CODE = getattr(settings, 'GAME_CURRENCY_CODE', 'USD')
    FORMAT = getattr(settings, 'GAME_CURRENCY_FORMAT', None)
    LOCALE = getattr(settings, 'GAME_CURRENCY_LOCALE', 'en_US')
    DECIMAL_PLACES = getattr(settings, 'GAME_CURRENCY_DECIMAL_PLACES', 2)

    CODE = getattr(settings, '')
    LOCALE = '...'
    DECIMAL_PLACES = 0
    FORMAT = '# points'


    def to_money(self, subsession):
        # subsession arg can actually be a session as well
        if isinstance(subsession, otree.session.models.Session):
            session = subsession
        else:
            session = subsession.session

        if settings.USE_POINTS:
            return Money(self * session.money_per_point)
        else:
            # should i convert to Money?
            return self



class _CurrencyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Money):
            return float(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)

def safe_json(obj):
    return mark_safe(json.dumps(obj, cls=_CurrencyEncoder))

# FIXME: there is a problem with currency = 0.01. this increment is too small if you use points.
# causes the function to hang.
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
