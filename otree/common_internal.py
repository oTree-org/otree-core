import hashlib
import os
import urllib
import urlparse
from decimal import Decimal
from os.path import dirname, join

import babel.numbers
from babel.core import Locale
from django import forms
from django.apps import apps
from django.conf import settings
from django.template.defaultfilters import title
from django.utils.importlib import import_module
from collections import OrderedDict



from otree import constants
from babel.numbers import format_currency
from django.conf import settings

class _CurrencyInput(forms.NumberInput):
     def _format_value(self, value):
         return str(Decimal(value))


def add_params_to_url(url, params):
    url_parts = list(urlparse.urlparse(url))

    # use OrderedDict because sometimes we want certain params at end for readability/consistency
    query = OrderedDict(urlparse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urllib.urlencode(query)
    return urlparse.urlunparse(url_parts)

def id_label_name(id, label):
    if label:
        return '{} (label: {})'.format(id, label)
    return '{}'.format(id)

def is_subsession_app(app_label):
    try:
        models_module = import_module('{}.models'.format(app_label))
    except ImportError:
        return False
    class_names = ['Player', 'Group', 'Subsession']
    return all(hasattr(models_module, ClassName) for ClassName in class_names)

def git_commit_timestamp():
    root_dir = dirname(settings.BASE_DIR)
    try:
        with open(join(root_dir, 'git_commit_timestamp'), 'r') as f:
            return f.read().strip()
    except IOError:
        return ''

def app_name_format(app_name):
    app_label = app_name.split('.')[-1]
    return title(app_label.replace("_", " "))

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

def get_session_module():
    base_dir_name = directory_name(settings.BASE_DIR)
    module_name = getattr(settings, 'SESSIONS_MODULE',
                          '{}.sessions'.format(base_dir_name))
    return import_module(module_name)

def get_models_module(app_name):
    return import_module('{}.models'.format(app_name))

def get_views_module(app_name):
    return import_module('{}.views'.format(app_name))

def get_app_constants(app_name):
    '''
    Return the ``Constants`` object of a app defined in the models.py file.

    Example::

        >>> from otree.subsessions import get_app_constants
        >>> get_app_constants('demo_game')
        <class demo_game.models.Constants at 0x7fed46bdb188>
    '''
    return get_models_module(app_name).Constants

def flatten(list_of_lists):
    return [item for sublist in list_of_lists for item in sublist]

def get_app_name_from_import_path(import_path):
    '''
    Return the registered otree app that contains the given module.

    >>> get_app_name_from_import_path('tests.simple_game.models')
    'tests.simple_game'
    >>> get_app_name_from_import_path('tests.simple_game.views.mixins.FancyMixin')
    'tests.simple_game'
    >>> get_app_name_from_import_path('unregistered_app.models')
    Traceback (most recent call last):
      File "<stdin>", line 1, in ?
    ValueError: The module unregistered_app.models is not part of any known otree app.
    '''
    app_name = import_path
    while app_name:
        if app_name in settings.INSTALLED_OTREE_APPS:
            return app_name
        if '.' in app_name:
            # Remove everything from the last dot.
            app_name = '.'.join(app_name.split('.')[:-1])
        else:
            app_name = None
    raise ValueError('The module {} is not part of any known otree app.'.format(import_path))


def get_app_name_from_label(app_label):
    '''
    >>> get_app_name_from_label('simple_game')
    'tests.simple_game'
    '''
    return apps.get_app_config(app_label).name

def get_players(self, refresh_from_db=False):
    if (not refresh_from_db) and hasattr(self, '_players'):
        return self._players
    # this means even subsession.players orders them by id_in_group, not necessarily optimal
    self._players = list(self.player_set.order_by('id_in_group'))
    return self._players

def get_groups(self, refresh_from_db=False):
    if (not refresh_from_db) and hasattr(self, '_groups'):
        return self._groups
    self._groups = list(self.group_set.all())
    return self._groups


def expand_choice_tuples(choices):
    '''allows the programmer to define choices as a list of values rather than (value, display_value)'''
    if not choices:
        return
    # look at the first element
    first_choice = choices[0]
    if not isinstance(first_choice, (list, tuple)):
        choices = [(value, value) for value in choices]
    return choices

