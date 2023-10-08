import gettext as gettext_lib
from otree.common import FULL_DECIMAL_PLACES
from otree import settings
import re


# these symbols are a fallback if we don't have an explicit rule
# for the currency/language combination.
# (most common situation is where the language is English)

CURRENCY_SYMBOLS = {
    'AED': 'AED',
    'ARS': '$',
    'AUD': '$',
    'BRL': 'R$',
    'CAD': '$',
    'CHF': 'CHF',
    # need to use yuan character here, that's what gets shown
    # on form inputs. but if you run a study in english, it will
    # still show 元, which is not ideal. but that is rare.
    'CNY': '元',
    'CZK': 'Kč',
    'DKK': 'kr',
    'EGP': 'ج.م.‏',
    'EUR': '€',
    'GBP': '£',
    'HKD': 'HK$',
    'HUF': 'Ft',
    'ILS': '₪',
    'INR': '₹',
    'JPY': '円',
    'KRW': '원',
    'MXN': '$',
    'MYR': 'RM',
    'NOK': 'kr',
    'PLN': 'zł',
    'RUB': '₽',
    'SEK': 'kr',
    'SGD': 'SGD',
    'THB': 'THB',
    'TRY': '₺',
    'TWD': '$',
    'USD': '$',
    'ZAR': 'R',
}


def get_currency_format(lc: str, LO: str, CUR: str) -> str:

    '''because of all the if statements, this has very low code coverage
    but it's ok'''

    ##############################
    # Languages with complex rules
    ##############################

    if lc == 'en':
        if CUR in ['USD', 'CAD', 'AUD']:
            return '$#'
        if CUR == 'GBP':
            return '£#'
        if CUR == 'EUR':
            return '€#'
        if CUR == 'INR':
            return '₹ #'
        if CUR == 'SGD':
            return '$#'
        # override for CNY/JPY/KRW, otherwise it would be written as 원10
        # need to use the chinese character because that's already what's used in
        # form inputs
        if CUR == 'CNY':
            return '#元'
        if CUR == 'JPY':
            return '#円'
        if CUR == 'KRW':
            return '#원'
        if CUR == 'ZAR':
            return 'R#'
        return '¤#'

    if lc == 'zh':
        if CUR == 'CNY':
            return '#元'
        if CUR == 'HKD':
            return 'HK$#'
        if CUR == 'TWD':
            return '$#'
        if CUR == 'SGD':
            return 'SGD#'
        return '¤#'

    if lc == 'de':
        if CUR == 'EUR':
            if LO == 'AT':
                return '€ #'
            return '# €'
        if CUR == 'CHF':
            return 'CHF #'
        return '¤ #'

    if lc == 'es':
        if CUR == 'ARS':
            return '$ #'
        if CUR == 'EUR':
            return '# €'
        if CUR == 'MXN':
            return '$#'
        return '# ¤'

    if lc == 'nl':
        if LO == 'BE':
            if CUR == 'EUR':
                return '# €'
            return '# ¤'
        # default NL
        if CUR == 'EUR':
            return '€ #'
        return '¤ #'

    if lc == 'pt':
        if CUR == 'BRL':
            return 'R$#'
        if CUR == 'EUR':
            return '# €'
        return '¤#'

    if lc == 'ar':
        if CUR == 'AED':
            return 'د.إ.‏ #'
        return '¤ #'

    #############################
    # Languages with simple rules
    #############################

    if lc == 'cs':
        if CUR == 'CZK':
            return '# Kč'
        return '# ¤'
    if lc == 'da':
        if CUR == 'DKK':
            return '# kr.'
        return '# ¤'
    if lc == 'fi':
        if CUR == 'EUR':
            return '# €'
        return '# ¤'
    if lc == 'fr':
        if CUR == 'EUR':
            return '# €'
        return '# ¤'
    if lc == 'he':
        if CUR == 'ILS':
            return '# ₪'
        return '# ¤'
    if lc == 'hu':
        if CUR == 'HUF':
            return '# Ft'
        return '# ¤'
    if lc == 'it':
        if CUR == 'EUR':
            return '# €'
        return '# ¤'
    if lc == 'ja':
        if CUR == 'JPY':
            return '#円'
        return '¤#'
    if lc == 'ko':
        if CUR == 'KRW':
            return '#원'
        return '¤#'
    if lc == 'ms':
        if CUR == 'MYR':
            return 'RM#'
        return '¤#'
    if lc == 'nb':
        if CUR == 'NOK':
            return 'kr #'
        return '¤ #'
    if lc == 'pl':
        if CUR == 'PLN':
            return '# zł'
        return '# ¤'
    if lc == 'ru':
        if CUR == 'RUB':
            return '# ₽'
        return '# ¤'
    if lc == 'sv':
        if CUR == 'SEK':
            return '# kr'
        return '# ¤'
    if lc == 'th':
        if CUR == 'THB':
            return '฿#'
        return '¤#'
    if lc == 'tr':
        if CUR == 'TRY':
            return '# ₺'
        return '# ¤'
    if lc == 'hi':
        if CUR == 'INR':
            return '₺#'
        return '¤#'

    # fallback if it's another language, etc.
    return '# ¤'


def format_number(number, *, places):
    """we don't use locale.setlocale because e.g.
    only english locale is installed on heroku

    This is a complex function because it's is used by many different things.
    - currency
    - formatting any number (random floats, etc)
    - forms
    - to0, to1, to2

    """
    # we use FULL_DECIMAL_PLACES as the arg because it's more explict than None.
    if places is FULL_DECIMAL_PLACES:
        places = None
    str_number = str(number)
    if '.' in str_number:
        lhs, rhs = str_number.split('.')
    else:
        lhs = str_number
        if places is None:
            return lhs
        rhs = ''
    if places is not None:
        rhs = rhs.ljust(places, '0')
    if places == 0:
        return lhs
    # rhs[:None] just takes the whole thing, which is the desired behavior
    # with floats.
    return lhs + settings.DECIMAL_SEPARATOR + rhs[:places]


def extract_otreetemplate(fileobj, keywords, comment_tags, options):
    """Deprecated"""
    for lineno, line in enumerate(fileobj, start=1):
        for msg in re.findall(r"""\{\{\s?trans ['"](.*)['"]\s?\}\}""", line.decode()):
            yield (lineno, 'trans', msg, [])


def extract_otreetemplate_internal(fileobj, keywords, comment_tags, options):
    """babel custom extractor for |gettext in otree templates"""
    for lineno, line in enumerate(fileobj, start=1):
        for msg in re.findall(
            r"""\{\{\s?['"](.*)['"]\|gettext\s?\}\}""", line.decode()
        ):
            # not sure exactly what the 2nd arg is for
            yield (lineno, 'gettext', msg, [])


def core_gettext(msg):
    return gettext_lib.dgettext('django', msg)


"""
Don't use core-ngettext because pybabel doesn't recognize that it is for
plurals 
"""
