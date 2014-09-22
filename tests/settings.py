DEBUG = False


ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'otree'
SECRET_KEY = 'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}


INSTALLED_APPS = (
    'floppyforms',
    'otree',
    'raven.contrib.django.raven_compat',
)


CURRENCY_CODE = 'USD'
LANGUAGE_CODE = 'en-us'


INSTALLED_OTREE_APPS = [
    'trust',
    'lab_results',
]
