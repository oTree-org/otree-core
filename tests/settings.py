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
    'floppyforms',

    'otree',

    'raven.contrib.django.raven_compat',
    'tests.demo',
)


CURRENCY_CODE = 'USD'
LANGUAGE_CODE = 'en-us'


ROOT_URLCONF = 'tests.demo.urls'


INSTALLED_OTREE_APPS = [
    'trust',
    'lab_results',
]
