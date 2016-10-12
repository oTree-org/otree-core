import os
from os import environ

import otree.settings
from django.conf.global_settings import STATICFILES_STORAGE  # noqa

from boto.mturk.qualification import LocaleRequirement
from boto.mturk.qualification import PercentAssignmentsApprovedRequirement
from boto.mturk.qualification import NumberHitsApprovedRequirement


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PRJ_DIR = os.path.dirname(BASE_DIR)

DEBUG = True

ADMIN_PASSWORD = 'otree'
SECRET_KEY = 'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz'

AUTH_LEVEL = ''

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

CREATE_DEFAULT_SUPERUSER = True
ADMIN_USERNAME = 'admin'
AWS_ACCESS_KEY_ID = None
AWS_SECRET_ACCESS_KEY = None

# e.g. EUR, CAD, GBP, CHF, CNY, JPY
REAL_WORLD_CURRENCY_CODE = 'EUR'
USE_POINTS = False


# e.g. en-gb, de-de, it-it, fr-fr.
# see: https://docs.djangoproject.com/en/1.7/topics/i18n/
LANGUAGE_CODE = 'en'

INSTALLED_APPS = [
    'otree',
    'raven.contrib.django.raven_compat',
    'tests',
]
mturk_hit_settings = {
    'keywords': ['easy', 'bonus', 'choice', 'study'],
    'title': 'Title for your experiment',
    'description': 'Description for your experiment',
    'frame_height': 500,
    'preview_template': 'global/MTurkPreview.html',
    'minutes_allotted_per_assignment': 60,
    'expiration_hours': 7*24,  # 7 days
    # to prevent retakes
    'grant_qualification_id': 'YOUR_QUALIFICATION_ID_HERE',
    'qualification_requirements': [
        LocaleRequirement("EqualTo", "US"),
        PercentAssignmentsApprovedRequirement("GreaterThanOrEqualTo", 50),
        NumberHitsApprovedRequirement("GreaterThanOrEqualTo", 5),
        # Requirement('YOUR_QUALIFICATION_ID_HERE', 'DoesNotExist'),
    ]
}


SESSION_CONFIG_DEFAULTS = {
    'real_world_currency_per_point': 0.01,
    'participation_fee': 10.00,
    'doc': "",
    'mturk_hit_settings': mturk_hit_settings,
}


SESSION_CONFIGS = [
    {
        'name': 'simple',
        'display_name': "Simple Game",
        'num_demo_participants': 1,
        'app_sequence': ['tests.simple'],
    },
    {
        'name': 'misc_1p',
        'display_name': "Single Player Game",
        'num_demo_participants': 1,
        'participation_fee': 9.99,
        'real_world_currency_per_point': 0.02,
        'app_sequence': ['tests.misc_1p'],
        'treatment': 'blue'
    },
    {
        'name': 'misc_3p',
        'display_name': "Multi Player Game",
        'num_demo_participants': 3,
        'app_sequence': ['tests.misc_3p'],
    },
    {
        "name": 'two_simple_games',
        "display_name": "2 Simple Games",
        "num_demo_participants": 1,
        "app_sequence": ['tests.simple', 'tests.misc_1p'],
    },
    {
        'name': 'skipmany',
        'display_name': "skip many",
        'num_demo_participants': 2,
        'app_sequence': ['tests.skip_many'],
    },
    {
        'name': 'rounds',
        'num_demo_participants': 4,
        'app_sequence': ['tests.rounds'],
    },
    {
        'name': 'advance_slowest',
        'num_demo_participants': 2,
        'app_sequence': ['tests.advance_slowest'],
    },
    {
        'name': 'advance_slowest_wait',
        'num_demo_participants': 2,
        'app_sequence': ['tests.advance_slowest_wait'],
    },
    {
        'name': 'wait_page',
        'num_demo_participants': 2,
        'app_sequence': ['tests.wait_page'],
    },
    {
        'name': 'skip_wait_page',
        'num_demo_participants': 2,
        'app_sequence': ['tests.skip_wait_page'],
    },
    {
        'name': 'export',
        'num_demo_participants': 1,
        'app_sequence': ['tests.export'],
    },
    {
        'name': 'bots',
        'num_demo_participants': 2,
        'app_sequence': ['tests.bots'],
    },
    {
        'name': 'bots_check_html',
        'num_demo_participants': 1,
        'app_sequence': ['tests.bots_check_html'],
    },
    {
        'name': 'bots_bad_post',
        'num_demo_participants': 1,
        'app_sequence': ['tests.bots_bad_post'],
    },
    {
        'name': 'templates_app',
        'num_demo_participants': 1,
        'app_sequence': ['tests.templates_app'],
    },
    {
        'name': 'two_rounds_1p',
        'num_demo_participants': 1,
        'app_sequence': ['tests.two_rounds_1p'],
        'real_world_currency_per_point': 0.5,
        'participation_fee': 1.25,
    },

]


ROOM_DEFAULTS = {}


ROOMS = [
    {
        'name': 'default',
        'display_name': 'Default',
        'participant_label_file': 'tests/participant_labels.txt',
        'use_secure_urls': False
    },
    {
        'name': 'anon',
        'display_name': 'Anonymous',
    },
]

BOTS_CHECK_HTML = False

otree.settings.augment_settings(globals())
