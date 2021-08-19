import html
from otree.i18n import core_gettext
from otree import common
from otree.currency import Currency, json_dumps, BaseCurrency
from otree.i18n import format_number

# Dictionary of registered filter functions.
filtermap = {}


# Decorator function for registering filters.  A filter function should accept at least one
# argument - the value to be filtered - and return the filtered result. It can optionally
# accept any number of additional arguments.
#
# This decorator can be used as:
#
#     @register
#     @register()
#     @register('name')
#
# If no name is supplied the function name will be used.
def register(nameorfunc=None):

    if callable(nameorfunc):
        filtermap[nameorfunc.__name__] = nameorfunc
        return nameorfunc

    def register_filter_function(func):
        filtermap[nameorfunc or func.__name__] = func
        return func

    return register_filter_function


@register
def default(obj, fallback):
    """ Returns `obj` if `obj` is truthy, otherwise `fallback`. """
    return obj or fallback


@register
def escape(s, quotes=True):
    """ Converts html syntax characters to character entities. """
    return html.escape(s, quotes)


@register
def length(seq):
    """ Returns the length of the sequence `seq`. """
    return len(seq)


@register('c')
@register('cu')
def currency_filter(val):
    return Currency(val)


@register
def safe(val):
    return val


@register
def gettext(val):
    return core_gettext(val)


@register
def json(val):
    return json_dumps(val)


def to_places(val, places):
    if isinstance(val, BaseCurrency):
        return val._format_currency(places=places)
    return format_number(val, places=places)


@register
def to0(val):
    return to_places(val, 0)


@register
def to1(val):
    return to_places(val, 1)


@register
def to2(val):
    return to_places(val, 2)


@register
def linebreaks(val):
    """|linebreaks was used in an old sample games.
    this is just a shim."""
    return val
