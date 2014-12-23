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

MIDDLEWARE_CLASSES = ()

ROOT_URLCONF = 'otree.default_urls'

SESSIONS_MODULE = 'tests.sessions'

ACCESS_CODE_FOR_OPEN_SESSION = 'idd1610'

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
        os.path.join(PRJ_DIR, "otree", "forms"),
        os.path.join(PRJ_DIR, "otree", "locale"),
        os.path.join(PRJ_DIR, "otree", "management"),
        os.path.join(PRJ_DIR, "otree", "migrations"),
        os.path.join(PRJ_DIR, "otree", "models"),
        os.path.join(PRJ_DIR, "otree", "session"),
        os.path.join(PRJ_DIR, "otree", "templatetags"),
        os.path.join(PRJ_DIR, "otree", "test"),
        os.path.join(PRJ_DIR, "otree", "timeout"),
        os.path.join(PRJ_DIR, "otree", "views"),


        os.path.join(PRJ_DIR, "otree", "widgets.py"),
        os.path.join(PRJ_DIR, "tests", "simple_game"),
        os.path.join(PRJ_DIR, "tests", "simple_game_copy"),
    )
}


otree.settings.augment_settings(globals())
