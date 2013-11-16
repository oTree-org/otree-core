__doc__ = """See https://docs.djangoproject.com/en/dev/howto/custom-template-tags/"""

from django import template
from babel.numbers import format_currency
from django.conf import settings
from decimal import Decimal

register = template.Library()

def currency(value):
    """Takes in a number of cents (int) and returns a formatted currency amount.
    """

    if value == None:
        return '?'
    value_in_major_units = Decimal(value)/(10**settings.CURRENCY_DECIMAL_PLACES)
    return format_currency(value_in_major_units, settings.CURRENCY_CODE, locale=settings.CURRENCY_LOCALE)

register.filter('currency',currency)