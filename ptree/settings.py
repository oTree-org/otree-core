from django.conf import settings
from collections import OrderedDict
import os
import django.conf
import django.contrib.sessions.serializers

def remove_duplicates(lst):
    return list(OrderedDict.fromkeys(lst))

def collapse_to_unique_list(*args):
    combined_list = []
    for arg in args:
        if arg is not None:
            combined_list += list(arg)
    return remove_duplicates(combined_list)

def augment_settings(settings):



    default_installed_apps = [
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'ptree.stuff',
    ]

    third_party_apps = ['data_exports', 'crispy_forms']

    # order is important:
    # ptree unregisters User & Group, which are installed by auth.
    # ptree templates need to get loaded before the admin.
    # but ptree also unregisters data_exports, which comes afterwards?
    new_installed_apps = collapse_to_unique_list(['django.contrib.auth',
                                                  'ptree',
                                                  'django.contrib.admin',],
                                                 default_installed_apps,
                                                 third_party_apps,
                                                 settings['INSTALLED_APPS'],
                                                 settings['INSTALLED_PTREE_APPS'])

    new_template_dirs = collapse_to_unique_list(
        [os.path.join(settings['BASE_DIR'], 'templates/')],
         settings.get('TEMPLATE_DIRS'))

    new_staticfiles_dirs = collapse_to_unique_list(settings.get('STATICFILES_DIRS'),
        [os.path.join(settings['BASE_DIR'], 'static')])

    new_middleware_classes = collapse_to_unique_list(
        ['django.middleware.common.CommonMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',],
        settings.get('MIDDLEWARE_CLASSES')
    )

    augmented_settings = {
        'INSTALLED_APPS': new_installed_apps,
        'TEMPLATE_DIRS': new_template_dirs,
        'STATICFILES_DIRS': new_staticfiles_dirs,
        'MIDDLEWARE_CLASSES': new_middleware_classes,
    }



    overridable_settings = {
        'CRISPY_TEMPLATE_PACK': 'bootstrap3',

        # pages with a time limit for the participant can have a grace period
        # to compensate for network latency.
        # the timer is started and stopped server-side,
        # so this grace period should account for time spent during
        # download, upload, page rendering, etc.
        'TIME_LIMIT_GRACE_PERIOD_SECONDS': 5,
        'SESSION_SAVE_EVERY_REQUEST': True,
        'TEMPLATE_DEBUG': settings['DEBUG'],
        'STATIC_ROOT': 'staticfiles',
        'STATIC_URL': '/static/',
        'CURRENCY_CODE': 'USD',
        'CURRENCY_LOCALE': 'en_US',
        'CURRENCY_DECIMAL_PLACES': 2,
        'TIME_ZONE': 'UTC',
        'SESSION_SERIALIZER': 'django.contrib.sessions.serializers.PickleSerializer',
    }


    settings.update(augmented_settings)

    for k,v in overridable_settings.items():
        if not settings.has_key(k):
            settings[k] = v





