import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CRISPY_TEMPLATE_PACK = 'bootstrap3'

# pages with a time limit for the participant can have a grace period
# to compensate for network latency.
# the timer is started and stopped server-side,
# so this grace period should account for time spent during
# download, upload, page rendering, etc.
TIME_LIMIT_GRACE_PERIOD_SECONDS = 5
SESSION_SAVE_EVERY_REQUEST = True
STATIC_ROOT = 'staticfiles'
STATIC_URL = '/static/'
CURRENCY_CODE = 'USD'
CURRENCY_LOCALE = 'en_US'
CURRENCY_DECIMAL_PLACES = 2
TIME_ZONE = 'UTC'
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer'
ALLOWED_HOSTS = ['*']


TEMPLATE_DIRS = [
    os.path.join(BASE_DIR, 'templates')
]

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static')
]

MIDDLEWARE_CLASSES = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware'
]

INSTALLED_APPS = [
    'django.contrib.auth',
    'ptree',
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'ptree.stuff',
    'data_exports',
    'crispy_forms'
]
