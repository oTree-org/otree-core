from gettext import gettext as original_gettext
from otree.currency import Currency
from ibis.filters import register
from otree.common import json_dumps

@register('c')
def currency_filter(val):
    return Currency(val)


@register
def safe(val):
    return val


@register
def gettext(val):
    return original_gettext(val)

@register
def json(val):
    return json_dumps(val)