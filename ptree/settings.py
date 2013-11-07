from settings import *
BUILT_IN_INSTALLED_APPS = ['ptree', 'data_exports', 'crispy_forms']
BUILT_IN_PTREE_NON_EXPERIMENT_APPS = ['ptree.questionnaires.life_orientation_test',]
BUILT_IN_PTREE_EXPERIMENT_APPS = []

def get_ptree_experiment_apps(USER_PTREE_EXPERIMENT_APPS):
    return USER_PTREE_EXPERIMENT_APPS + BUILT_IN_PTREE_EXPERIMENT_APPS

def get_ptree_non_experiment_apps(USER_PTREE_NON_EXPERIMENT_APPS):
    return USER_PTREE_NON_EXPERIMENT_APPS + BUILT_IN_PTREE_NON_EXPERIMENT_APPS

def get_ptree_apps(USER_PTREE_EXPERIMENT_APPS, USER_PTREE_NON_EXPERIMENT_APPS):
    return get_ptree_experiment_apps(USER_PTREE_EXPERIMENT_APPS) + \
           get_ptree_non_experiment_apps(USER_PTREE_NON_EXPERIMENT_APPS)

def get_installed_apps(USER_INSTALLED_APPS, USER_PTREE_EXPERIMENT_APPS, USER_PTREE_NON_EXPERIMENT_APPS):
    INSTALLED_APPS = USER_INSTALLED_APPS + BUILT_IN_INSTALLED_APPS
    return INSTALLED_APPS + get_ptree_apps(USER_PTREE_EXPERIMENT_APPS, USER_PTREE_NON_EXPERIMENT_APPS)

CRISPY_TEMPLATE_PACK = 'bootstrap3'

# pages with a time limit for the participant can have a grace period
# to compensate for network latency.
# the timer is started and stopped server-side,
# so this grace period should account for time spent during
# download, upload, page rendering, etc.
TIME_LIMIT_GRACE_PERIOD_SECONDS = 15

SESSION_SAVE_EVERY_REQUEST = True

TEMPLATE_DIRS = (

)

TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, 'templates/'),
    'ptree/templates',
)


# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
)

STATIC_ROOT = 'staticfiles'
STATIC_URL = '/static/'

SESSION_EXPIRE_AT_BROWSER_CLOSE = True

TEMPLATE_DEBUG = DEBUG