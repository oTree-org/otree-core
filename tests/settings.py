import os
import otree.settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PRJ_DIR = os.path.dirname(BASE_DIR)

TEST_VERBOSITY = 2

DEBUG = True

ADMIN_PASSWORD = 'otree'
SECRET_KEY = 'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz'

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
PAYMENT_CURRENCY_CODE = 'EUR'
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

INSTALLED_OTREE_APPS = [
    'tests.simple_game',
    'tests.simple_game_copy',
]

SESSION_TYPE_DEFAULTS = {
    'money_per_point': 0.01,
    'demo_enabled': True,
    'fixed_pay': 10.00,
    'num_bots': 12,
    'doc': "",
    'group_by_arrival_time': False,
}


SESSION_TYPES = [
    {
        'name': 'simple_game',
        'display_name': "Simple Game",
        'num_demo_participants': 1,
        'app_sequence': ['tests.simple_game'],
        'doc': ""
    },
    {
        "name": 'two_simple_games',
        "display_name": "2 Simple Games",
        "num_demo_participants": 1,
        "app_sequence": ['tests.simple_game', 'tests.simple_game_copy'],
        "doc": ""
    },
]


DEMO_PAGE_INTRO_TEXT = """
<ul>
    <li>
        <a href="https://github.com/oTree-org/otree" target="_blank">
            Source code
        </a>
        for the below games.
    </li>
    <li>
        <a href="http://www.otree.org/" target="_blank">oTree homepage</a>.
    </li>
</ul>
<p>
    Below are various games implemented with oTree. These games are all open
    source, and you can modify them as you wish to create your own variations.
    Click one to learn more and play.
</p>
"""


MIDDLEWARE_CLASSES = ()

ROOT_URLCONF = 'otree.default_urls'

ACCESS_CODE_FOR_DEFAULT_SESSION = 'idd1610'

PEP8 = {
    "check": (
        os.path.join(PRJ_DIR, "otree"),
        os.path.join(PRJ_DIR, "tests"),
        os.path.join(PRJ_DIR, "runtests.py"),
        os.path.join(PRJ_DIR, "setup.py"),
        os.path.join(PRJ_DIR, "manage.py"),
    ),
    "exclude": (
        os.path.join(PRJ_DIR, "otree", "app_template"),
        os.path.join(PRJ_DIR, "otree", "locale"),
        os.path.join(PRJ_DIR, "otree", "migrations"),
        os.path.join(PRJ_DIR, "otree", "session", "migrations"),
        os.path.join(PRJ_DIR, "tests", "simple_game"),
        os.path.join(PRJ_DIR, "tests", "simple_game_copy"),
    )
}


otree.settings.augment_settings(globals())
