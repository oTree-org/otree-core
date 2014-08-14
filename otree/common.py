import babel.numbers
from django.conf import settings
from decimal import Decimal
import urllib
import urlparse
from django.utils.importlib import import_module
import subprocess
from django.template.defaultfilters import title
from otree import constants
import os
import hashlib
from os.path import dirname, abspath, join
from ast import literal_eval
import copy
from easymoney import Money
from django import forms

from decimal import Decimal

# R: Should not be needed
class _MoneyInput(forms.NumberInput):
     def _format_value(self, value):
         return str(Decimal(value))


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
    class_names = ['Player', 'Match', 'Treatment', 'Subsession']
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

def _views_module(model_instance):
    return import_module('{}.views'.format(model_instance._meta.app_label))

class ModelWithCheckpointMixin(object):

    def _initialize_checkpoints(self):
        views_module = _views_module(self)
        CheckpointMixinClass = self._CheckpointMixinClass()
        player_ids = {str(p.pk):True for p in self.player_set.all()}
        # i+1 because of WaitUntilPlayerAssignedToMatch
        self._incomplete_checkpoints = {str(i+1):player_ids for i, C in enumerate(views_module.pages()) if issubclass(C, CheckpointMixinClass)}


    def _record_checkpoint_visit(self, index_in_pages, player_id):
        '''returns whether to take the action'''
        _incomplete_checkpoints = copy.deepcopy(self._incomplete_checkpoints)
        index_in_pages = str(index_in_pages)
        player_id = str(player_id)
        take_action = False
        if _incomplete_checkpoints.has_key(index_in_pages):
            remaining_visits = _incomplete_checkpoints[index_in_pages]
            if remaining_visits.has_key(player_id):
                remaining_visits.pop(player_id, None)
                if not remaining_visits:
                    take_action = True
        self._incomplete_checkpoints = _incomplete_checkpoints
        self.save()
        return take_action

    def _mark_checkpoint_complete(self, index_in_pages):
        index_in_pages = str(index_in_pages)
        _incomplete_checkpoints = copy.deepcopy(self._incomplete_checkpoints)
        _incomplete_checkpoints.pop(index_in_pages)
        self._incomplete_checkpoints = _incomplete_checkpoints

    def _checkpoint_is_complete(self, index_in_pages):
        index_in_pages = str(index_in_pages)
        return not self._incomplete_checkpoints.has_key(index_in_pages)

    def _refresh_with_lock(self):
        return self.__class__._default_manager.select_for_update().get(pk=self.pk)

def _players(self):
    if hasattr(self, '_players'):
        return self._players
    self._players = list(self.player_set.order_by('index_among_players_in_match'))
    return self._players

def _matches(self):
    if hasattr(self, '_matches'):
        return self._matches
    self._matches = list(self.match_set.all())
    return self._matches

def money_range(first, last, increment=Money(0.01)):
    assert last >= first
    assert increment >= 0
    values = []
    current_value = Money(first)
    while True:
        if current_value > last:
            return values
        values.append(current_value)
        current_value += increment

def expand_choice_tuples(choices):
    '''allows the programmer to define choices as a list of values rather than (value, display_value)'''
    if not choices:
        return
    # look at the first element
    first_choice = choices[0]
    if not isinstance(first_choice, (list, tuple)):
        choices = [(value, value) for value in choices]
    return choices
