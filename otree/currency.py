'''
Vendored version of django-easymoney.
Putting directly in otree-core because PyCharm flags certain usages in yellow,
like:

    c(1) + c(1)

Results in: "Currency does not define __add__, so the + operator cannot
be used on its instances"

If "a" is a CurrencyField, then
    self.a + c(1)

PyCharm warns: 'Currency does not define __add__, so the + operator cannot
be used on its instances'

    c(1) + 1

'Expected type "int", got "Currency" instead'

    self.a + 1

'Expected type "int", got "CurrencyField" instead'

easymoney's Money and MoneyField don't have any of these problems.

Other reasons:
- We have to override certain things anyway; it's easier to keep track of
when it's imported indirectly.
- As far as I know, we are the only users of EasyMoney
- If I want to make a fix, I can do it immediately, rather than making a pull
request and waiting for the change upstream.

'''

from django.utils import formats, numberformat
from django.utils.translation import ungettext

import sys
from decimal import Decimal, ROUND_HALF_UP

import babel.core
import babel.numbers
from django import forms
from django.conf import settings
import six

# =============================================================================
# MONKEY PATCH - fix for https://github.com/oTree-org/otree-core/issues/387
# =============================================================================

# Black Magic: The original number format of django used inside templates don't
# work if the currency code contains non-ascii characters. This ugly hack
# remplace the original number format and when you has a easy_money instance
# simple use the old unicode casting.

_original_number_format = numberformat.format


def otree_number_format(number, *args, **kwargs):
    if isinstance(number, Currency):
        return six.text_type(number)
    return _original_number_format(number, *args, **kwargs)

numberformat.format = otree_number_format


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
        )


def _make_binary_operator(name):
    method = getattr(Decimal, name, None)
    def binary_function(self, other, context=None):
        other = _prepare_operand(self, other)
        return self.__class__(method(self, other))
    return binary_function


def format_currency(number, currency, format, locale=babel.numbers.LC_NUMERIC,
                    force_frac=None, format_type='standard'):
    """Same as ``babel.numbers.format_currency``, but has ``force_frac``
    argument instead of ``currency_digits``.

    If the ``force_frac`` argument is given, the argument is passed down to
    ``pattern.apply``.
    """
    locale = babel.core.Locale.parse(locale)
    if format:
        pattern = babel.numbers.parse_pattern(format)
    else:
        try:
            pattern = locale.currency_formats[format_type]
        except KeyError:
            raise babel.numbers.UnknownCurrencyFormatError(
                "%r is not a known currency format type" % format_type)
    if force_frac is None:
        fractions = babel.core.get_global('currency_fractions')
        try:
            digits = fractions[currency][0]
        except KeyError:
            digits = fractions['DEFAULT'][0]
        frac = (digits, digits)
    else:
        frac = force_frac
    return pattern.apply(number, locale, currency=currency, force_frac=frac)


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
        return self._format_currency(Decimal(self))

    def __str__(self):
        string = self._format_currency(Decimal(self))
        if six.PY2:
            return string.encode('utf-8')
        return string

    @classmethod
    def _format_currency(cls, number):
        return format_currency(
            number=number,
            currency=settings.REAL_WORLD_CURRENCY_CODE,
            locale=settings.REAL_WORLD_CURRENCY_LOCALE,
            format=None,
            force_frac=(
                cls.MIN_DECIMAL_PLACES,
                settings.REAL_WORLD_CURRENCY_DECIMAL_PLACES)
        )

    def __format__(self, format_spec):
        if format_spec in {'', 's'}:
            formatted = six.text_type(self)
        else:
            formatted = format(Decimal(self), format_spec)

        if isinstance(format_spec, six.binary_type):
            return formatted.encode('utf-8')
        else:
            return formatted

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, Decimal.__str__(self))

    def __eq__(self, other):
        if isinstance(other, BaseCurrency):
            return Decimal.__eq__(self, other)
        elif isinstance(other, six.integer_types + (float, Decimal)):
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

    def deconstruct(self):
        return '{}.{}'.format(self.__module__, self.__class__.__name__), \
               [Decimal.__str__(self)], {}

    def to_number(self):
        '''
        Deprecated. This has trivial functionality; it's not clear from the API
        whether this returns a float or Decimal. Better to let the user do it explicitly
        '''
        return Decimal(self)

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
                float(self) *
                session.config['real_world_currency_per_point'])
        else:
            return self

    def _format_currency(cls, number):
        if settings.USE_POINTS:

            formatted_number = formats.number_format(number)

            if hasattr(settings, 'POINTS_CUSTOM_NAME'):
                return '{} {}'.format(
                    formatted_number, settings.POINTS_CUSTOM_NAME)

            # Translators: display a number of points,
            # like "1 point", "2 points", ...
            # See "Plural-Forms" above for pluralization rules
            # in this language.
            # Explanation at http://bit.ly/1IurMu7
            # In most languages, msgstr[0] is singular,
            # and msgstr[1] is plural
            # the {} represents the number;
            # don't forget to include it in your translation
            return ungettext('{} point', '{} points', number).format(
                formatted_number)
        else:
            return super()._format_currency(number)


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

def stdout_encode(u, default='UTF8'):
    if sys.stdout.encoding:
        return u.encode(sys.stdout.encoding)
    return u.encode(default)