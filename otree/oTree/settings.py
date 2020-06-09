from os import environ, path

import os
import dj_database_url

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="https://bc756496e8a64eefa6cef54d7899ff0e@o397173.ingest.sentry.io/5251429",
    integrations=[DjangoIntegration()],

    # If you wish to associate users to errors (assuming you are using
    # django.contrib.auth) you may enable sending PII data.
    send_default_pii=True
)

# if you set a property in SESSION_CONFIG_DEFAULTS, it will be inherited by all configs
# in SESSION_CONFIGS, except those that explicitly override it.
# the session config can be accessed from methods in your apps as self.session.config,
# e.g. self.session.config['participation_fee']

REAL_WORLD_CURRENCY_CODE = 'EUR'
USE_POINTS = False

SESSION_CONFIG_DEFAULTS = dict(
    real_world_currency_per_point=0.00, participation_fee=0.00, doc=""
)

SESSION_CONFIGS = [
    dict(
        name='bad_influence',
        display_name="Bad Influence",
        num_demo_participants=5,
        app_sequence=['bad_influence'],
        use_secure_urls=True
    ),
    dict(
        name='daytrader',
        display_name="Daytrader",
        num_demo_participants=3,
        app_sequence=['daytrader'],
    ),
]

# ISO-639 code
# for example: de, fr, ja, ko, zh-hansSubsession
LANGUAGE_CODE = 'da'

TIME_ZONE = 'Europe/Copenhagen'
USE_TZ = False

ROOMS = [
    dict(
        name='live_demo',
        display_name='Room for live demo (no participant labels)'),
    dict(
        name='test',
        display_name='Test Room',
    )
]

ADMIN_USERNAME = 'admin'
# for security, best to set admin password in an environment variable
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')

DEMO_PAGE_INTRO_HTML = """
Here are some oTree games.
"""

# don't share this with anybody.
SECRET_KEY = 'dn$$a-!!1z(!%*&p*ad*tqx=pidp84@he0x8^rn_@o$27pov2*'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'otree',
    'bad_influence',
    'daytrader',
]

EXTENSION_APPS = [
    'bad_influence',
    'daytrader'
]

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "../otree/static/main_platform/otree")
]

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "../otree/static/main_platform/otree")
]

MEDIA_URL = 'media/'

MEDIA_ROOT = 'bad_influence/static/main_platform'
DATABASES = {'default': dj_database_url.config(default='sqlite:///' + os.path.join(BASE_DIR, 'db.sqlite3'))}

# TODO - Skal ændres til den rigtige mailserver
EMAIL_HOST = 'send.one.com'

EMAIL_PORT = 587

EMAIL_HOST_USER = 'frederikabruun@pmat.dk'

EMAIL_HOST_PASSWORD = 'Django123456'

EMAIL_USE_TLS = True

DEFAULT_FROM_EMAIL = 'Frederik Bruun <frederikabruun@pmat.dk>'

# Defines the location of the new abstract user class
AUTH_USER_MODEL = 'otree.User'

LOGIN_EXEMPT_URLS = (
    r'',
)

LOGIN_REDIRECT_URL = '/spil/'

LOGIN_URL = '/accounts/login/'
