import babel.numbers
from django.conf import settings
from decimal import Decimal
import urllib
import urlparse
from django.utils.importlib import import_module
import subprocess
from django.template.defaultfilters import title
from ptree import constants
import os
import hashlib
from os.path import dirname, abspath, join


def add_params_to_url(url, params):
    url_parts = list(urlparse.urlparse(url))
    query = dict(urlparse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urllib.urlencode(query)
    return urlparse.urlunparse(url_parts)

def id_label_name(id, label):
    if label:
        return '{} (label: {})'.format(id, label)
    return '{}'.format(id)

def currency(value):
    """Takes in a number of cents (int) and returns a formatted currency amount.
    """

    if value == None:
        return '?'
    value_in_major_units = Decimal(value)/(10**settings.CURRENCY_DECIMAL_PLACES)
    return babel.numbers.format_currency(value_in_major_units, settings.CURRENCY_CODE, locale=settings.CURRENCY_LOCALE)

def is_subsession_app(app_label):
    try:
        models_module = import_module('{}.models'.format(app_label))
    except ImportError:
        return False
    class_names = ['Participant', 'Match', 'Treatment', 'Subsession']
    return all(hasattr(models_module, ClassName) for ClassName in class_names)

def git_commit_timestamp():
    root_dir = dirname(settings.BASE_DIR)
    try:
        with open(join(root_dir, 'git_commit_timestamp'), 'r') as f:
            return f.read().strip()
    except IOError:
        return ''

def app_name_format(app_name):
    return title(app_name.replace("_", " "))

def url(cls, session_user, index=None):
    u = '/{}/{}/{}/{}/'.format(
        session_user.user_type_in_url,
        session_user.code,
        cls.get_name_in_url(),
        cls.__name__,
    )

    if index is not None:
        u += '{}/'.format(index)
    return u

def url_pattern(cls, is_sequence_url=False):
    p = r'(?P<{}>\w)/(?P<{}>[a-z]+)/{}/{}/'.format(
        constants.user_type,
        constants.session_user_code,
        cls.get_name_in_url(),
        cls.__name__,
    )
    if is_sequence_url:
        p += r'(?P<{}>\d+)/'.format(constants.index_in_pages,)
    p = r'^{}$'.format(p)
    return p

def directory_name(path):
    return os.path.basename(os.path.normpath(path))

def access_code_for_open_session():
    hash = hashlib.sha1()
    hash.update(settings.SECRET_KEY)
    return hash.hexdigest()

def get_session_module():
    return import_module('{}.session'.format(directory_name(settings.BASE_DIR)))

def get_models_module(app_name):
    return import_module('{}.models'.format(app_name))

def flatten(list_of_lists):
    return [item for sublist in list_of_lists for item in sublist]
