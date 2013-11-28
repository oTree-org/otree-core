import os
from ptree.settings import *

# You'll want to override these in production.
DEBUG = True
TEMPLATE_DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# You shouldn't need to change these.
WSGI_APPLICATION = '{{ project_name }}.wsgi.application'
ROOT_URLCONF = '{{ project_name }}.urls'

# Automatically create a superuser during syncdb.
CREATE_DEFAULT_SUPERUSER = True
ADMIN_USERNAME = 'ptree'
ADMIN_PASSWORD = 'ptree'

# Get AWS credentials from enviroment variables.
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

# Don't share this with anybody.
# Change this to something unique (e.g. mash your keyboard), and then delete this comment.
SECRET_KEY = 'zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz'

# This setting is required for ptree to determine which URLs
# to automatically add to the project.
INSTALLED_PTREE_APPS = []

# Ensure we add in any ptree apps to Django's standard 'INSTALLED_APPS' setting.
INSTALLED_APPS += INSTALLED_PTREE_APPS

# If you need to install other third party apps or middleware,
# it's best to append these to the existing set of defaults,
# so that the default set of ptree requirements are left as-is.
# INSTALLED_APPS += []
# MIDDLEWARE_CLASSES += []