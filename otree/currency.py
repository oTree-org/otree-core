from gettext import dngettext
import json
from decimal import Decimal, ROUND_HALF_UP

from otree import settings
from otree.i18n import (
    CURRENCY_SYMBOLS,
    get_currency_format,
    format_number,
)


# Set up money arithmetic
def _to_decimal(amount):
    if isinstance(amount, Decimal):
        return amount
    elif isinstance(amount, float):
        return Decimal.from_float(amount)
    else:
        return Decimal(amount)


def _make_unary_operator(name):
    method = getattr(Decimal, name, None)
    # NOTE: current context would be used anyway, so we can just ignore it.
    #       Newer pythons don't have that, keeping this for compatability.
    return lambda self, context=None: self.__class__(method(self))


def _prepare_operand(self, other):
    try:
        return _to_decimal(other)
    except:
        raise TypeError(
            "Cannot do arithmetic operation between "
            "{} and {}.".format(repr(self), repr(other))
        ) from None


def _make_binary_operator(name):
    method = getattr(Decimal, name, None)

    def binary_function(self, other, context=None):
        other = _prepare_operand(self, other)
        return self.__class__(method(self, other))

    return binary_function


# Data class


class BaseCurrency(Decimal):

    # what's this for?? can't money have any # of decimal places?
    MIN_DECIMAL_PLACES = 2

    def __new__(cls, amount):
        if amount is None:
            raise ValueError('Cannot convert None to currency')
        return Decimal.__new__(cls, cls._sanitize(amount))

    @classmethod
    def _sanitize(cls, amount):
        if isinstance(amount, cls):
            return amount
        quant = Decimal('0.1') ** cls.get_num_decimal_places()
        return _to_decimal(amount).quantize(quant, rounding=ROUND_HALF_UP)

    # Support for pickling
    def __reduce__(self):
        return (self.__class__, (Decimal.__str__(self),))

    # Money is immutable
    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self

    def __float__(self):
        """Float representation."""
        return float(Decimal(self))

    def __unicode__(self):
        return self._format_currency()

    def __str__(self):
        string = self._format_currency()
        return string

    def _format_currency(self, places=None):
        if places is None:
            places = self.get_num_decimal_places()
        number = Decimal(self)
        LANGUAGE_CODE = settings.LANGUAGE_CODE
        if '-' in LANGUAGE_CODE:
            lc, LO = LANGUAGE_CODE.split('-')
        else:
            lc, LO = LANGUAGE_CODE, ''
        return format_currency(
            number, lc=lc, LO=LO, CUR=settings.REAL_WORLD_CURRENCY_CODE, places=places
        )

    def __format__(self, format_spec):
        """needed if you use eg. f-strings in .py code"""
        if format_spec in {'', 's'}:
            formatted = str(self)
        else:
            formatted = format(Decimal(self), format_spec)

        if isinstance(format_spec, bytes):
            return formatted.encode('utf-8')
        else:
            return formatted

    def __repr__(self):
        return f'{Decimal.__str__(self)}cu'

    def __eq__(self, other):
        if isinstance(other, BaseCurrency):
            return Decimal.__eq__(self, other)
        elif isinstance(other, (int, float, Decimal)):
            return Decimal.__eq__(self, self._sanitize(other))
        else:
            return False

    # for Python 3:
    # need to re-define __hash__ because we defined __eq__ above
    # https://docs.python.org/3.5/reference/datamodel.html#object.%5F%5Fhash%5F%5F
    __hash__ = Decimal.__hash__

    # Special casing this, cause it have extra modulo arg
    def __pow__(self, other, modulo=None):
        other = _prepare_operand(self, other)
        return self.__class__(Decimal.__pow__(self, other, modulo))

    __abs__ = _make_unary_operator('__abs__')
    __pos__ = _make_unary_operator('__pos__')
    __neg__ = _make_unary_operator('__neg__')

    __add__ = _make_binary_operator('__add__')
    __radd__ = _make_binary_operator('__radd__')
    __sub__ = _make_binary_operator('__sub__')
    __rsub__ = _make_binary_operator('__rsub__')
    __mul__ = _make_binary_operator('__mul__')
    __rmul__ = _make_binary_operator('__rmul__')
    __floordiv__ = _make_binary_operator('__floordiv__')
    __rfloordiv__ = _make_binary_operator('__rfloordiv__')
    __truediv__ = _make_binary_operator('__truediv__')
    __rtruediv__ = _make_binary_operator('__rtruediv__')
    if hasattr(Decimal, '__div__'):
        __div__ = _make_binary_operator('__div__')
        __rdiv__ = _make_binary_operator('__rdiv__')
    __mod__ = _make_binary_operator('__mod__')
    __rmod__ = _make_binary_operator('__rmod__')
    __divmod__ = _make_binary_operator('__divmod__')
    __rdivmod__ = _make_binary_operator('__rdivmod__')
    __rpow__ = _make_binary_operator('__rpow__')

    @classmethod
    def get_num_decimal_places(cls):
        raise NotImplementedError()


class Currency(BaseCurrency):
    @classmethod
    def get_num_decimal_places(cls):
        if settings.USE_POINTS:
            return settings.POINTS_DECIMAL_PLACES
        else:
            return settings.REAL_WORLD_CURRENCY_DECIMAL_PLACES

    def to_real_world_currency(self, session):
        if settings.USE_POINTS:
            return RealWorldCurrency(
                float(self) * session.config['real_world_currency_per_point']
            )
        else:
            return self

    def _format_currency(self, places=None):
        number = Decimal(self)
        if settings.USE_POINTS:

            formatted_number = f'{number:n}'
            if getattr(settings, 'POINTS_CUSTOM_NAME', None):
                return f'{formatted_number} {settings.POINTS_CUSTOM_NAME}'

            # Translators: display a number of points,
            # like "1 point", "2 points", ...
            # See "Plural-Forms" above for pluralization rules
            # in this language.
            # Explanation at http://bit.ly/1IurMu7
            # In most languages, msgstr[0] is singular,
            # and msgstr[1] is plural
            # the {} represents the number;
            # don't forget to include it in your translation
            return dngettext('django', '{} point', '{} points', number).format(
                formatted_number
            )
        else:
            return super()._format_currency(places=places)


class RealWorldCurrency(BaseCurrency):
    '''payment currency'''

    def to_real_world_currency(self, session):
        return self

    @classmethod
    def get_num_decimal_places(cls):
        return settings.REAL_WORLD_CURRENCY_DECIMAL_PLACES


# Utils


def to_dec(value):
    return Decimal(value) if isinstance(value, Currency) else value


def format_currency(number, lc, LO, CUR, places):
    symbol = CURRENCY_SYMBOLS.get(CUR, CUR)
    c_format = get_currency_format(lc, LO, CUR)
    number_part = format_number(abs(number), places=places)
    retval = c_format.replace('¤', symbol).replace('#', number_part)
    if number < 0:
        return '-' + retval
    return retval


def currency_range(first, last, increment):
    assert last >= first
    if Currency(increment) == 0:
        if settings.USE_POINTS:
            setting_name = 'POINTS_DECIMAL_PLACES'
        else:
            setting_name = 'REAL_WORLD_CURRENCY_DECIMAL_PLACES'
        raise ValueError(
            (
                'currency_range() step argument must not be zero. '
                'Maybe your {} setting is '
                'causing it to be rounded to 0.'
            ).format(setting_name)
        )

    assert increment > 0  # not negative

    values = []
    current_value = Currency(first)

    while True:
        if current_value > last:
            return values
        values.append(current_value)
        current_value += increment


class _CurrencyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (Currency, RealWorldCurrency)):
            if obj.get_num_decimal_places() == 0:
                return int(obj)
            return float(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


def json_dumps(obj):
    return json.dumps(obj, cls=_CurrencyEncoder)


def safe_json(obj):
    return json_dumps(obj)
