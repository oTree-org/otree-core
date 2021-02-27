import gettext as gettext_lib

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
            return 'THB#'
        return '¤#'
    if lc == 'tr':
        if CUR == 'TRY':
            return '# ₺'
        return '# ¤'

    # fallback if it's another language, etc.
    return '# ¤'


def format_number(number, places=None):
    """we don't use locale.setlocale because e.g.
    only english locale is installed on heroku
    """
    str_number = str(number)
    if '.' in str_number:
        lhs, rhs = str_number.split('.')
        if places == 0:
            return lhs
        return lhs + settings.DECIMAL_SEPARATOR + rhs[:places]
    return str_number


def extract_otreetemplate(fileobj, keywords, comment_tags, options):
    """babel custom extractor for {% trans %} tag in otree templates"""
    for lineno, line in enumerate(fileobj, start=1):
        for msg in re.findall(r"""\{%\s?trans ['"](.*)['"]\s?%\}""", line.decode()):
            yield (lineno, 'trans', msg, [])


def gettext(msg):
    return gettext_lib.dgettext('django', msg)


def ngettext(msg1, msg2, n):
    return gettext_lib.dngettext('django', msg1, msg2, n)
