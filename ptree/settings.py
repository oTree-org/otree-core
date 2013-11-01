BUILT_IN_INSTALLED_APPS = ('ptree', 'ptree.models', 'data_exports', 'crispy_forms')
BUILT_IN_PTREE_NON_EXPERIMENT_APPS = ('ptree.questionnaires.life_orientation_test',)
BUILT_IN_PTREE_EXPERIMENT_APPS = ()

def get_ptree_experiment_apps(USER_PTREE_EXPERIMENT_APPS):
    return USER_PTREE_EXPERIMENT_APPS + BUILT_IN_PTREE_EXPERIMENT_APPS

def get_ptree_non_experiment_apps(USER_PTREE_NON_EXPERIMENT_APPS):
    return USER_PTREE_NON_EXPERIMENT_APPS + BUILT_IN_PTREE_NON_EXPERIMENT_APPS

def get_ptree_apps(USER_PTREE_EXPERIMENT_APPS, USER_PTREE_NON_EXPERIMENT_APPS):
    return get_ptree_experiment_apps(USER_PTREE_EXPERIMENT_APPS) + \
           get_ptree_non_experiment_apps(USER_PTREE_NON_EXPERIMENT_APPS)

def get_installed_apps(USER_INSTALLED_APPS, USER_PTREE_EXPERIMENT_APPS, USER_PTREE_NON_EXPERIMENT_APPS):
    INSTALLED_APPS = BUILT_IN_INSTALLED_APPS + USER_INSTALLED_APPS
    return INSTALLED_APPS + get_ptree_apps(USER_PTREE_EXPERIMENT_APPS, USER_PTREE_NON_EXPERIMENT_APPS)

CRISPY_TEMPLATE_PACK = 'bootstrap3'

# pages with a time limit for the participant can have a grace period
# to compensate for network latency.
# the timer is started and stopped server-side,
# so this grace period should account for time spent during
# download, upload, page rendering, etc.
TIME_LIMIT_GRACE_PERIOD_SECONDS = 15
SESSION_SAVE_EVERY_REQUEST = True