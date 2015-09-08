"""oTree Public API utilities"""

import json
from decimal import Decimal

from django.conf import settings
import django.utils.formats
from django.utils.safestring import mark_safe
from django.utils.translation import ungettext

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
        DECIMAL_PLACES = settings.POINTS_DECIMAL_PLACES

    def __format__(self, format_spect):
        return super(Currency, self).__format__('s')

    @classmethod
    def _format_currency(cls, number):
        if settings.USE_POINTS:

            formatted_number = django.utils.formats.number_format(number)

            if hasattr(settings, 'POINTS_CUSTOM_FORMAT'):
                return settings.POINTS_CUSTOM_FORMAT.format(formatted_number)

            # Translators: display a number of points,
            # like "1 point", "2 points", ...
            # See "Plural-Forms" above for pluralization rules
            # in this language.
            # Explanation at http://bit.ly/1IurMu7
            # In most languages, msgstr[0] is singular,
            # and msgstr[1] is plural
            return ungettext('{} point', '{} points', number).format(
                formatted_number
            )
        return super(Currency, cls)._format_currency(number)

    def to_real_world_currency(self, session):

        if settings.USE_POINTS:
            return RealWorldCurrency(
                self.to_number() *
                session.config['real_world_currency_per_point'])
        else:
            return self


class _CurrencyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, easymoney.Money):
            return float(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


def safe_json(obj):
    return mark_safe(json.dumps(obj, cls=_CurrencyEncoder))


def currency_range(first, last, increment):
    assert last >= first
    if Currency(increment) == 0:
        if settings.USE_POINTS:
            setting_name = 'POINTS_DECIMAL_PLACES'
        else:
            setting_name = 'REAL_WORLD_CURRENCY_DECIMAL_PLACES'
        raise ValueError(
            ('currency_range() step argument must not be zero. '
             'Maybe your {} setting is '
            'causing it to be rounded to 0.').format(setting_name)
        )

    values = []
    current_value = Currency(first)

    while True:
        if current_value > last:
            return values
        values.append(current_value)
        current_value += increment
