import os
import otree.settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PRJ_DIR = os.path.dirname(BASE_DIR)

DEBUG = True

ADMIN_PASSWORD = 'otree'
SECRET_KEY = 'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz'

AUTH_LEVEL = os.environ.get('OTREE_AUTH_LEVEL', 'DEMO')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

CREATE_DEFAULT_SUPERUSER = True
ADMIN_USERNAME = 'admin'
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

# e.g. EUR, CAD, GBP, CHF, CNY, JPY
REAL_WORLD_CURRENCY_CODE = 'EUR'
USE_POINTS = False


# e.g. en-gb, de-de, it-it, fr-fr.
# see: https://docs.djangoproject.com/en/1.7/topics/i18n/
LANGUAGE_CODE = 'en-us'

INSTALLED_APPS = [
    'otree',
    'raven.contrib.django.raven_compat',
    'tests',
    'tests.demo',
]


SESSION_CONFIG_DEFAULTS = {
    'real_world_currency_per_point': 0.01,
    'participation_fee': 10.00,
    'num_bots': 12,
    'doc': "",
    'group_by_arrival_time': False,
}


SESSION_CONFIGS = [
    {
        'name': 'simple_game',
        'display_name': "Simple Game",
        'num_demo_participants': 1,
        'app_sequence': ['tests.simple_game'],
    },
    {
        'name': 'single_player_game',
        'display_name': "Single Player Game",
        'num_demo_participants': 1,
        'num_bots': 1,
        'participation_fee': 9.99,
        'real_world_currency_per_point': 0.02,
        'app_sequence': ['tests.single_player_game'],
        'treatment': 'blue'
    },
    {
        'name': 'multi_player_game',
        'display_name': "Multi Player Game",
        'num_demo_participants': 3,
        'num_bots': 6,
        'app_sequence': ['tests.multi_player_game'],
    },
    {
        "name": 'two_simple_games',
        "display_name": "2 Simple Games",
        "num_demo_participants": 1,
        "app_sequence": ['tests.simple_game', 'tests.single_player_game'],
    },
]


DEMO_PAGE_INTRO_TEXT = """"""


ACCESS_CODE_FOR_DEFAULT_SESSION = 'idd1610'


MTURK_WORKER_REQUIREMENTS = []


otree.settings.augment_settings(globals())
