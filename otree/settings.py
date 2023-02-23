import os.path
import sys


DEBUG = os.environ.get('OTREE_PRODUCTION') in [None, '', '0']
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AUTH_LEVEL = os.environ.get('OTREE_AUTH_LEVEL')
REAL_WORLD_CURRENCY_CODE = 'USD'
USE_POINTS = True
POINTS_DECIMAL_PLACES = 0
POINTS_CUSTOM_NAME = None  # define it so we can patch it
ADMIN_PASSWORD = os.environ.get('OTREE_ADMIN_PASSWORD', '')
MTURK_NUM_PARTICIPANTS_MULTIPLE = 2
BOTS_CHECK_HTML = True
PARTICIPANT_FIELDS = []
SESSION_FIELDS = []

# Add the current directory to sys.path so that Python can find
# the settings module.
# when using "python manage.py" this is not necessary because
# the entry-point script's dir is automatically added to sys.path.
# but the 'otree' command script is located outside of the project
# directory.
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())


try:
    import settings
    from settings import *
except ModuleNotFoundError as exc:
    if exc.name == 'settings':
        msg = (
            "Cannot find oTree settings. "
            "Please 'cd' to your oTree project folder, "
            "which contains a settings.py file."
        )
        sys.exit(msg)
    raise


def get_OTREE_APPS(SESSION_CONFIGS):
    from itertools import chain

    app_sequences = [s['app_sequence'] for s in SESSION_CONFIGS]
    return list(dict.fromkeys(chain(*app_sequences)))


OTREE_APPS = get_OTREE_APPS(settings.SESSION_CONFIGS)
if not hasattr(settings, 'REAL_WORLD_CURRENCY_DECIMAL_PLACES'):
    if REAL_WORLD_CURRENCY_CODE in [
        'KRW',
        'JPY',
        'HUF',
        'IRR',
        'COP',
        'VND',
        'IDR',
    ]:
        REAL_WORLD_CURRENCY_DECIMAL_PLACES = 0
    else:
        REAL_WORLD_CURRENCY_DECIMAL_PLACES = 2


def get_locale_name(language_code):
    if language_code == 'zh-hans':
        return 'zh_Hans'
    parts = language_code.split('-')
    if len(parts) == 2:
        return parts[0] + '_' + parts[1].upper()
    return language_code


LANGUAGE_CODE_ISO = get_locale_name(LANGUAGE_CODE)


def get_decimal_separator(lc):

    if lc in ['en', 'ja', 'ko', 'ms', 'th', 'zh']:
        return '.'
    else:
        return ','


DECIMAL_SEPARATOR = get_decimal_separator(LANGUAGE_CODE[:2])
