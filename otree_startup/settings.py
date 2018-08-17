import os
import os.path
from django.contrib.messages import constants as messages
from six.moves.urllib import parse as urlparse
import dj_database_url

DEFAULT_MIDDLEWARE = (
    'otree.middleware.CheckDBMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',

    # 2015-04-08: disabling SSLify until we make this work better
    # 'sslify.middleware.SSLifyMiddleware',
)


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


def get_default_settings(user_settings: dict):
    '''
    doesn't mutate user_settings, just reads from it
    because some settings depend on others
    '''
    default_settings = {}

    if user_settings.get('SENTRY_DSN'):
        default_settings['RAVEN_CONFIG'] = {
            'dsn': user_settings['SENTRY_DSN'],
            'processors': ['raven.processors.SanitizePasswordsProcessor'],
        }
        # SentryHandler is very slow with URL resolving...can add 2 seconds
        # to runserver startup! so only use when it's needed
        sentry_handler_class = 'raven.contrib.django.raven_compat.handlers.SentryHandler'
    else:
        sentry_handler_class = 'logging.StreamHandler'

    logging = {
        'version': 1,
        'disable_existing_loggers': False,
        'root': {
            'level': 'DEBUG',
            'handlers': ['console'],
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
                'formatter': 'simple'
            },
            'sentry': {
                'level': 'WARNING',
                # perf issue. just use StreamHandler by default.
                # only use the real sentry handler if a DSN exists.
                # see below.
                'class': sentry_handler_class,

            },
        },
        'loggers': {
            'otree.test.core': {
                'handlers': ['console'],
                'propagate': False,
                'level': 'INFO',
            },
            # 2016-07-25: botworker seems to be sending messages to Sentry
            # without any special configuration, not sure why.
            # but, i should use a logger, because i need to catch exceptions
            # in botworker so it keeps running
            'otree.test.browser_bots': {
                'handlers': ['sentry', 'console'],
                'propagate': False,
                'level': 'INFO',
            },
            'django.request': {
                'handlers': ['console'],
                'propagate': True,
                'level': 'DEBUG',
            },
            # logger so that we can explicitly send certain warnings to sentry,
            # without raising an exception.
            # 2016-10-23: has not been used yet
            'otree.sentry': {
                'handlers': ['sentry'],
                'propagate': True,
                'level': 'DEBUG',
            },
            # log any error that occurs inside channels code
            'django.channels': {
                'handlers': ['sentry'],
                'propagate': True,
                'level': 'ERROR',
            },
            # This is required for exceptions inside Huey tasks to get logged
            # to Sentry
            'huey.consumer': {
                'handlers': ['sentry', 'console'],
                'level': 'INFO'
            },
            # suppress the INFO message: 'raven is not configured (logging
            # disabled).....', in case someone doesn't have a DSN
            'raven.contrib.django.client.DjangoClient': {
                'handlers': ['console'],
                'level': 'WARNING'
            }


        }
    }

    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    redis_url_parsed = urlparse.urlparse(REDIS_URL)
    BASE_DIR = user_settings.get('BASE_DIR', '')


    default_settings.update({
        'DATABASES': {
            'default': dj_database_url.config(
                default='sqlite:///' + os.path.join(BASE_DIR, 'db.sqlite3')
            )
        },
        'HUEY': {
            'name': 'otree-huey',
            'connection': {
                'host': redis_url_parsed.hostname,
                'port': redis_url_parsed.port,
                'password': redis_url_parsed.password
            },
            'always_eager': False,
            # I need a result store to retrieve the results of browser-bots
            # tasks and pinging, even if the result is evaluated immediately
            # (otherwise, calling the task returns None.
            'result_store': False,
            'consumer': {
                'workers': 1,
                # 'worker_type': 'thread',
                'scheduler_interval': 5,
                'loglevel': 'warning',
            },
        },
        # set to True so that if there is an error in an {% include %}'d
        # template, it doesn't just fail silently. instead should raise
        # an error (and send through Sentry etc)
        'STATIC_ROOT': os.path.join(BASE_DIR, '__temp_static_root'),
        'STATIC_URL': '/static/',
        'STATICFILES_STORAGE': (
            'whitenoise.django.GzipManifestStaticFilesStorage'
        ),
        'ROOT_URLCONF': 'otree.urls',

        'TIME_ZONE': 'UTC',
        'USE_TZ': True,
        'ALLOWED_HOSTS': ['*'],

        'LOGGING': logging,

        'FORM_RENDERER':  'django.forms.renderers.TemplatesSetting',

        'REAL_WORLD_CURRENCY_CODE': 'USD',
        'REAL_WORLD_CURRENCY_DECIMAL_PLACES': 2,
        'USE_POINTS': True,
        'POINTS_DECIMAL_PLACES': 0,

        # eventually can remove this,
        # when it's present in otree-library
        # that most people downloaded
        'USE_L10N': True,
        'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),

        # The project can override the routing.py used as entry point by
        # setting CHANNEL_ROUTING.

        'CHANNEL_LAYERS': {
            'default': {
                "BACKEND": "otree.channels.asgi_redis.RedisChannelLayer",
                "CONFIG": {
                    "hosts": [REDIS_URL],
                },
                'ROUTING': user_settings.get(
                    'CHANNEL_ROUTING',
                    'otree.channels.routing.channel_routing'),
            },
            # note: if I start using ChannelsLiveServerTestCase again,
            # i might have to move this out,
            # but because it doesn't work with multiple
            # channel layers.
            'inmemory': {
                "BACKEND": "asgiref.inmemory.ChannelLayer",
                'ROUTING': user_settings.get(
                    'CHANNEL_ROUTING',
                    'otree.channels.routing.channel_routing'),
            },
        },

        # for convenience within oTree
        'REDIS_URL': REDIS_URL,

        # since workers on Amazon MTurk can return the hit
        # we need extra participants created on the
        # server.
        # The following setting is ratio:
        # num_participants_server / num_participants_mturk
        'MTURK_NUM_PARTICIPANTS_MULTIPLE': 2,
        'LOCALE_PATHS': [
            os.path.join(user_settings.get('BASE_DIR', ''), 'locale')
        ],

        # ideally this would be a per-app setting, but I don't want to
        # pollute Constants. It doesn't make as much sense per session config,
        # so I'm just going the simple route and making it a global setting.
        'BOTS_CHECK_HTML': True,
    })
    return default_settings



class InvalidVariableError(Exception):
    pass


class InvalidTemplateVariable(str):
    def get_error_message(self, variable_name_dotted: str):
        bits = variable_name_dotted.split('.')
        if len(bits) == 1:
            return (
                'Invalid variable: "{}". '
                'Maybe you need to return it from vars_for_template()'
            ).format(bits[0])

        built_in_vars = [
            'player',
            'group',
            'subsession',
            'participant',
            'session',
            'Constants',
        ]

        if bits[0] in built_in_vars:
            # This will not make sense in the admin report!
            # but that's OK, it's a rare case, more advanced users
            return (
                '{} has no attribute "{}"'
            ).format(bits[0], '.'.join(bits[1:]))
        elif bits[0] == 'self' and bits[1] in built_in_vars:
            return (
                "Don't use 'self' in the template. "
                "Just write: {}"
            ).format('.'.join(bits[1:]))
        else:
            return 'Invalid variable: {}'.format(variable_name_dotted)

    def __mod__(self, other):
        '''hack that takes advantage of string_if_invalid's %s behavior'''
        msg = self.get_error_message(str(other))
        # "from None" because otherwise we get the full chain of
        # checking if it's an attribute, dict key, list index ...
        raise InvalidVariableError(msg) from None

def augment_settings(settings: dict):
    default_settings = get_default_settings(settings)
    for k, v in default_settings.items():
        settings.setdefault(k, v)

    all_otree_apps_set = set()

    for s in settings['SESSION_CONFIGS']:
        for app in s['app_sequence']:
            all_otree_apps_set.add(app)

    all_otree_apps = list(all_otree_apps_set)

    no_experiment_apps = [
        'otree',

        # django.contrib.auth is slow, about 300ms.
        # would be nice to only add it if there is actually a password
        # i tried that but would need to add various complicated "if"s
        # throughout the code
        'django.contrib.auth',
        'django.forms',
        # needed for auth and very quick to load
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        # need to keep this around indefinitely for all the people who
        # have {% load staticfiles %}
        'django.contrib.staticfiles',
        'channels',
        'huey.contrib.djhuey',
        'idmap',
    ]

    # these are slow...only add if we need them
    if settings.get('RAVEN_CONFIG'):
        no_experiment_apps.append('raven.contrib.django.raven_compat')

    # order is important:
    # otree unregisters User & Group, which are installed by auth.
    # otree templates need to get loaded before the admin.
    no_experiment_apps = collapse_to_unique_list(
        no_experiment_apps,
        settings['INSTALLED_APPS'],
        settings.get('EXTENSION_APPS', [])
    )

    new_installed_apps = collapse_to_unique_list(
        no_experiment_apps, all_otree_apps)

    # TEMPLATES
    _template_dir = os.path.join(settings['BASE_DIR'], '_templates')
    if os.path.exists(_template_dir):
        new_template_dirs = [_template_dir]
    else:
        new_template_dirs = []

    # STATICFILES
    _static_dir = os.path.join(settings['BASE_DIR'], '_static')

    if os.path.exists(_static_dir):
        additional_static_dirs = [_static_dir]
    else:
        additional_static_dirs = []

    new_staticfiles_dirs = collapse_to_unique_list(
        settings.get('STATICFILES_DIRS'),
        additional_static_dirs,
    )

    new_middleware = collapse_to_unique_list(
        DEFAULT_MIDDLEWARE,
        settings.get('MIDDLEWARE_CLASSES'))

    augmented_settings = {
        'INSTALLED_APPS': new_installed_apps,
        'TEMPLATES': [{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': new_template_dirs,
            'OPTIONS': {
                # 2016-10-08: setting template debug back to True,
                # because if an included template has an error, we need
                # to surface the error, rather than not showing the template.
                # that's how I set it in d1cd00ebfd43c7eff408dea6363fd14bb90e7c06,
                # but then in 2c10188b33f2ac36c046f4f0f8764e15d6a6fa81,
                # i set this to False, but I'm not sure why and there is no
                # note in the commit explaining why.
                'debug': True,
                'string_if_invalid': InvalidTemplateVariable("%s"),

                # in Django 1.11, the cached template loader is applied
                # automatically if template 'debug' is False,
                # but for now we need 'debug' True because otherwise
                # {% include %} fails silently.
                # in django 2.1, we can remove:
                # - the explicit 'debug': True
                # - 'loaders' below
                # - the patch in runserver.py
                # as long as we set 'APP_DIRS': True
                'loaders': [
                    ('django.template.loaders.cached.Loader', [
                        'django.template.loaders.filesystem.Loader',
                        'django.template.loaders.app_directories.Loader',
                    ]),
                ],
                'context_processors': (
                    # default ones in Django 1.8
                    'django.contrib.auth.context_processors.auth',
                    'django.template.context_processors.media',
                    'django.template.context_processors.static',
                    'django.contrib.messages.context_processors.messages',
                    'django.template.context_processors.request',
                 )
            },
        }],
        'STATICFILES_DIRS': new_staticfiles_dirs,
        'MIDDLEWARE': new_middleware,
        'INSTALLED_OTREE_APPS': all_otree_apps,
        'MESSAGE_TAGS': {messages.ERROR: 'danger'},
        'LOGIN_REDIRECT_URL': 'Sessions',
    }

    settings.update(augmented_settings)
