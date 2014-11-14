import os
from django.conf import global_settings


def collapse_to_unique_list(*args):
    """Create a new list with all elements from a given lists without reapeated
    elements

    """
    combined = []
    for arg in args:
        for elem in arg or ():
            if elem not in combined:
                combined.append(elem)
    return combined


def augment_settings(settings):

    default_installed_apps = [
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'otree.session',
        'otree.models_concrete',
    ]

    # order is important:
    # otree unregisters User & Group, which are installed by auth.
    # otree templates need to get loaded before the admin.
    new_installed_apps = collapse_to_unique_list(
        [
            'django.contrib.auth', 'otree',
            'floppyforms','django.contrib.admin'
        ],
        default_installed_apps, settings['INSTALLED_APPS'],
        settings['INSTALLED_OTREE_APPS']
    )

    new_template_dirs = collapse_to_unique_list(
        [
            os.path.join(settings['BASE_DIR'], 'templates/')
        ],
        settings.get('TEMPLATE_DIRS')
    )

    new_staticfiles_dirs = collapse_to_unique_list(
        settings.get('STATICFILES_DIRS'),
        [
            os.path.join(settings['BASE_DIR'], 'static')
        ]
    )

    new_middleware_classes = collapse_to_unique_list(
        [
            'django.contrib.sessions.middleware.SessionMiddleware',
            #'django.middleware.locale.LocaleMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware'
        ],
        settings.get('MIDDLEWARE_CLASSES')
    )

    augmented_settings = {
        'INSTALLED_APPS': new_installed_apps,
        'TEMPLATE_DIRS': new_template_dirs,
        'STATICFILES_DIRS': new_staticfiles_dirs,
        'MIDDLEWARE_CLASSES': new_middleware_classes,
    }


    settings.setdefault('LANGUAGE_CODE', global_settings.LANGUAGE_CODE)

    CURRENCY_LOCALE = settings.get('CURRENCY_LOCALE', None)
    if not CURRENCY_LOCALE:

        # favor en_GB currency formatting since it represents negative amounts
        # with minus signs rather than parentheses
        if settings['LANGUAGE_CODE'][:2] == 'en':
            CURRENCY_LOCALE = 'en_GB'
        else:
            CURRENCY_LOCALE = settings['LANGUAGE_CODE']

    settings.setdefault('CURRENCY_LOCALE', CURRENCY_LOCALE.replace('-','_'))

    logging = {
        'version': 1,
        'disable_existing_loggers': False,
        'root': {
            'level': 'DEBUG',
            'handlers': ['console']
        },
        'formatters': {
            'verbose': {
                'format': '[%(levelname)s|%(asctime)s] %(name)s > %(message)s'
            },
            'simple': {
                'format': '%(levelname)s %(message)s'
            },
        },
        'handlers': {
            'console':{
                'level':'INFO',
                'class':'logging.StreamHandler',
                'formatter': 'verbose'
            },
        },
        'loggers': {
            'otree.test.core':{
                'handlers': ['console'],
                'propagate': False,
                'level': 'INFO',
            },
        }
    }

    overridable_settings = {

        # pages with a time limit for the player can have a grace period
        # to compensate for network latency.
        # the timer is started and stopped server-side,
        # so this grace period should account for time spent during
        # download, upload, page rendering, etc.
        'TIME_LIMIT_LATENCY_ALLOWANCE_SECONDS': 10,

        'SESSION_SAVE_EVERY_REQUEST': True,
        'TEMPLATE_DEBUG': settings['DEBUG'],
        'STATIC_ROOT': 'staticfiles',
        'STATIC_URL': '/static/',
        'ROOT_URLCONF': 'otree.default_urls',

        'TIME_ZONE': 'UTC',
        'USE_TZ': True,
        'SESSION_SERIALIZER': (
            'django.contrib.sessions.serializers.PickleSerializer'
        ),
        'ALLOWED_HOSTS': ['*'],
        'OTREE_CHANGE_LIST_COLUMN_MIN_WIDTH': 50, # In pixels
        'OTREE_CHANGE_LIST_UPDATE_INTERVAL': '10000', # default to 10 seconds(10000 miliseconds)
        'TEMPLATE_CONTEXT_PROCESSORS': (
            global_settings.TEMPLATE_CONTEXT_PROCESSORS +
            ('django.core.context_processors.request',)
        ),
        'SESSIONS_MODULE': 'sessions',
        'LOGGING': logging,

        'PAYMENT_CURRENCY_CODE': 'USD',
        'PAYMENT_CURRENCY_LOCALE': 'en_US',
        'PAYMENT_CURRENCY_FORMAT': None,
        'PAYMENT_CURRENCY_DECIMAL_PLACES': 2,
    }


    settings.update(augmented_settings)

    for k, v in overridable_settings.items():
        settings.setdefault(k,v)

    # by default, game setting matches payment setting
    # except if you use points, then we override
    if settings.get('USE_POINTS'):
        settings['GAME_CURRENCY_CODE'] = 'points'
        settings['GAME_CURRENCY_FORMAT'] = u'# points'
        settings['GAME_CURRENCY_DECIMAL_PLACES'] = 0
    else:
        for SETTING_NAME in ['CODE', 'FORMAT', 'LOCALE', 'DECIMAL_PLACES']:
            CURRENCY_SETTING_NAME = 'CURRENCY_{}'.format(SETTING_NAME)
            settings['GAME_{}'.format(CURRENCY_SETTING_NAME)] = settings['PAYMENT_{}'.format(CURRENCY_SETTING_NAME)]

