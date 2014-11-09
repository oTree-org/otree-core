"""oTree Public API utilities"""

from easymoney import Money, stdout_encode, _sanitize
from django.utils.safestring import mark_safe
import json
import otree.common_internal
from django.conf import settings
from decimal import Decimal
import otree.session.models


class Currency(Money):

    def __new__(cls, amount):
        """if we don't define this method, instantiating the class returns a Money object rather than a Currency object"""
        return Decimal.__new__(Currency, _sanitize(amount))

    def __repr__(self):
        return stdout_encode(u'Currency(%s)' % self)

    def to_money_decimal(self, subsession):
        # subsession arg can actually be a session as well
        if isinstance(subsession, otree.session.models.Session):
            session = subsession
        else:
            session = subsession.session

        amt = Decimal(self)
        if settings.USE_POINTS:
            amt *= session.money_per_point
        return amt

    def to_money_string(self, subsession):
        return otree.common_internal.format_payment_currency(self.to_money_decimal(subsession))

class _CurrencyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Currency):
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
