import os


BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))


DEBUG = True


ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'otree'
SECRET_KEY = 'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}


STATIC_URL = '/static/'


INSTALLED_APPS = (
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'otree',

    # floppyforms need to come after 'otree' in order to load the correct
    # form templates.
    'floppyforms',

    'raven.contrib.django.raven_compat',
    'tests.demo',
)


CURRENCY_CODE = 'USD'
CURRENCY_LOCALE = 'en_US'
LANGUAGE_CODE = 'en-us'


ROOT_URLCONF = 'tests.demo.urls'


INSTALLED_OTREE_APPS = [
    'trust',
    'lab_results',
]
