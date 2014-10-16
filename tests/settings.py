import os
import otree.settings


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEBUG = True

ADMIN_PASSWORD = 'otree'
SECRET_KEY = 'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz'

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
CURRENCY_CODE = 'EUR'

# e.g. en-gb, de-de, it-it, fr-fr. see: https://docs.djangoproject.com/en/1.6/topics/i18n/
LANGUAGE_CODE = 'en-us'

INSTALLED_APPS = [
    'otree',
    'raven.contrib.django.raven_compat',
    'tests',
    'tests.demo',
]

INSTALLED_OTREE_APPS = []

ROOT_URLCONF = 'tests.urls'

SESSION_MODULE = 'tests.session'


otree.settings.augment_settings(globals())
