#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import warnings

import djcelery

from django.conf import global_settings
from django.contrib.messages import constants as messages

djcelery.setup_loader()


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

    # 2015-07-10: SESSION_TYPE is deprecated
    if (('SESSION_CONFIGS' not in settings) and
            ('SESSION_TYPES' in settings)):
        # FIXME: this is not getting displayed
        msg = ('SESSION_TYPES is deprecated; '
               'you should rename it to "SESSION_CONFIGS".')
        warnings.warn(msg, DeprecationWarning)

        settings['SESSION_CONFIGS'] = settings['SESSION_TYPES']

    if (('SESSION_CONFIG_DEFAULTS' not in settings) and
            ('SESSION_TYPE_DEFAULTS' in settings)):
        msg = ('SESSION_TYPE_DEFAULTS is deprecated; '
               'you should rename it to "SESSION_CONFIG_DEFAULTS".')
        warnings.warn(msg, DeprecationWarning)
        settings['SESSION_CONFIG_DEFAULTS'] = settings['SESSION_TYPE_DEFAULTS']

    if 'POINTS_CUSTOM_NAME' in settings:
        settings.setdefault(
            'POINTS_CUSTOM_FORMAT',
            '{} ' + settings['POINTS_CUSTOM_NAME']
        )

    all_otree_apps_set = set()
    for s in settings['SESSION_CONFIGS']:
        for app in s['app_sequence']:
            all_otree_apps_set.add(app)
    all_otree_apps = list(all_otree_apps_set)

    # order is important:
    # otree unregisters User & Group, which are installed by auth.
    # otree templates need to get loaded before the admin.
    no_experiment_apps = collapse_to_unique_list([
        'django.contrib.auth',
        'otree',
        'floppyforms',
        # need this for admin login
        'django.contrib.admin',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'otree.models_concrete',
        'otree.timeout',
        'djcelery',
        'kombu.transport.django',
        'rest_framework',
        'sslserver',
        'idmap',
        'corsheaders'], settings['INSTALLED_APPS'])

    new_installed_apps = collapse_to_unique_list(
        no_experiment_apps, all_otree_apps)

    additional_template_dirs = []
    template_dir = os.path.join(settings['BASE_DIR'], 'templates')
    # 2015-09-21: i won't put a deprecation warning because 'templates/'
    # is the django convention and someone might legitimately want it.
    # just remove this code at some point
    # same for static/ dir below
    if os.path.exists(template_dir):
        additional_template_dirs = [template_dir]

    _template_dir = os.path.join(settings['BASE_DIR'], '_templates')
    if os.path.exists(_template_dir):
        additional_template_dirs = [_template_dir]

    new_template_dirs = collapse_to_unique_list(
        settings.get('TEMPLATE_DIRS'),
        # 2015-5-2: 'templates' is deprecated in favor of '_templates'
        # remove it at some point
        additional_template_dirs,
    )

    static_dir = os.path.join(settings['BASE_DIR'], 'static')
    additional_static_dirs = []
    if os.path.exists(static_dir):
        additional_static_dirs = [static_dir]

    _static_dir = os.path.join(settings['BASE_DIR'], '_static')
    if os.path.exists(_static_dir):
        additional_static_dirs = [_static_dir]

    new_staticfiles_dirs = collapse_to_unique_list(
        settings.get('STATICFILES_DIRS'),
        # 2015-5-2: 'static' is deprecated in favor of '_static'
        # remove it at some point
        additional_static_dirs,
    )

    new_middleware_classes = collapse_to_unique_list(
        [
            # this middlewware is for generate human redeable errors
            'otree.middleware.CheckDBMiddleware',
            'otree.middleware.HumanErrorMiddleware',
            # 2015-08-19: temporarily commented out because
            # a user got this error: http://dpaste.com/3E7JKCP
            # 'otree.middleware.DebugTableMiddleware',

            # alwaws before CommonMiddleware
            'corsheaders.middleware.CorsMiddleware',

            'django.contrib.sessions.middleware.SessionMiddleware',
            # 'django.middleware.locale.LocaleMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
            # 2015-04-08: disabling SSLify until we make this work better
            # 'sslify.middleware.SSLifyMiddleware',
        ],
        settings.get('MIDDLEWARE_CLASSES')
    )

    augmented_settings = {
        'INSTALLED_APPS': new_installed_apps,
        'TEMPLATE_DIRS': new_template_dirs,
        'STATICFILES_DIRS': new_staticfiles_dirs,
        'MIDDLEWARE_CLASSES': new_middleware_classes,
        'NO_EXPERIMENT_APPS': no_experiment_apps,
        'INSTALLED_OTREE_APPS': all_otree_apps,
        'BROKER_URL': 'django://',
        'MESSAGE_TAGS': {messages.ERROR: 'danger'},
        'CELERY_ACCEPT_CONTENT': ['pickle', 'json', 'msgpack', 'yaml'],
        'LOGIN_REDIRECT_URL': 'admin_home',
    }

    # CORS CONFS
    augmented_settings.update({
        'CORS_ORIGIN_ALLOW_ALL': True,
        'CORS_URLS_REGEX': r'^ping/$',
        'CORS_ALLOW_METHODS': ('GET',)
    })

    settings.setdefault('LANGUAGE_CODE', global_settings.LANGUAGE_CODE)

    CURRENCY_LOCALE = settings.get('CURRENCY_LOCALE', None)
    if not CURRENCY_LOCALE:

        # favor en_GB currency formatting since it represents negative amounts
        # with minus signs rather than parentheses
        if settings['LANGUAGE_CODE'][:2] == 'en':
            CURRENCY_LOCALE = 'en_GB'
        else:
            CURRENCY_LOCALE = settings['LANGUAGE_CODE']

    settings.setdefault('CURRENCY_LOCALE', CURRENCY_LOCALE.replace('-', '_'))

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
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose'
            },
        },
        'loggers': {
            'otree.test.core': {
                'handlers': ['console'],
                'propagate': False,
                'level': 'INFO',
            },
        }
    }

    page_footer = (
        'Powered By <a href="http://otree.org" target="_blank">oTree</a>'
    )

    overridable_settings = {

        # pages with a time limit for the player can have a grace period
        # to compensate for network latency.
        # the timer is started and stopped server-side,
        # so this grace period should account for time spent during
        # download, upload, page rendering, etc.
        'TIMEOUT_LATENCY_ALLOWANCE_SECONDS': 10,

        'SESSION_SAVE_EVERY_REQUEST': True,
        'TEMPLATE_DEBUG': settings['DEBUG'],
        'STATIC_ROOT': 'staticfiles',
        'STATIC_URL': '/static/',
        'STATICFILES_STORAGE': (
            'whitenoise.django.GzipManifestStaticFilesStorage'
        ),
        'ROOT_URLCONF': 'otree.default_urls',

        'TIME_ZONE': 'UTC',
        'USE_TZ': True,
        'SESSION_SERIALIZER': (
            'django.contrib.sessions.serializers.PickleSerializer'
        ),
        'ALLOWED_HOSTS': ['*'],

        'TEMPLATE_CONTEXT_PROCESSORS': (
            global_settings.TEMPLATE_CONTEXT_PROCESSORS +
            (
                'django.core.context_processors.request',
                'otree.context_processors.otree_context'
            )
        ),

        # SEO AND FOOTER
        'PAGE_FOOTER': page_footer,

        # list of extra string to positioning you experiments on search engines
        # Also if you want to add a particular set of SEO words to a particular
        # page add to template context "page_seo" variable.
        # See: http://en.wikipedia.org/wiki/Search_engine_optimization
        'SEO': (),

        'LOGGING': logging,

        'REAL_WORLD_CURRENCY_CODE': 'USD',
        'REAL_WORLD_CURRENCY_LOCALE': 'en_US',
        'REAL_WORLD_CURRENCY_DECIMAL_PLACES': 2,

        'POINTS_DECIMAL_PLACES': 0,

        # eventually can remove this,
        # when it's present in otree-library
        # that most people downloaded
        'USE_L10N': True,

        'WSGI_APPLICATION': 'otree.wsgi.application',
        'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),
        'MTURK_HOST': 'mechanicalturk.amazonaws.com',
        'MTURK_SANDBOX_HOST': 'mechanicalturk.sandbox.amazonaws.com',
        'CREATE_DEFAULT_SUPERUSER': True,

        'CELERY_APP': 'otree.celery.app:app',

        # since workers on Amazon MTurk can return the hit
        # we need extra participants created on the
        # server.
        # The following setting is ratio:
        # num_participants_server / num_participants_mturk
        'MTURK_NUM_PARTICIPANTS_MULT': 2,
    }

    settings.update(augmented_settings)

    for k, v in overridable_settings.items():
        settings.setdefault(k, v)

    # this guarantee that the test always run on memory
    if 'test' in sys.argv:
        settings["DATABASES"] = {
            "default": {
                "ENGINE": 'django.db.backends.sqlite3',
                "NAME": ':memory:'
            }
        }
        settings["DEBUG"] = False
        settings["TEMPLATE_DEBUG"] = False
