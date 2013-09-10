__doc__ = """See https://docs.djangoproject.com/en/dev/howto/custom-template-tags/"""

from django import template

import decimal

register = template.Library()

def currency(value):
    """Takes in a number of cents (int) and returns a formatted currency amount.
    Right now is hardcoded for dollars, but can easily be changed.
    """
    TWOPLACES = decimal.Decimal(10) ** -2
    return "$" + str((decimal.Decimal(value)/100).quantize(TWOPLACES))
register.filter('currency',currency)