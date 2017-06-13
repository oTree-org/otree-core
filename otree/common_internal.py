#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import

import hashlib
import logging
import os
import random
import re
import string
import uuid
from collections import OrderedDict
from importlib import import_module
from os.path import dirname, join

import channels
import six
from django.apps import apps
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import connection
from django.http import HttpResponseRedirect
from django.template.defaultfilters import title
from django.utils.safestring import mark_safe
from six.moves import urllib
from huey.contrib.djhuey import HUEY
import contextlib
from django.db import transaction
# set to False if using runserver
USE_REDIS = True


def add_params_to_url(url, params):
    url_parts = list(urllib.parse.urlparse(url))

    # use OrderedDict because sometimes we want certain params at end
    # for readability/consistency
    query = OrderedDict(urllib.parse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urllib.parse.urlencode(query)
    return urllib.parse.urlunparse(url_parts)


def id_label_name(id, label):
    if label:
        return '{} (label: {})'.format(id, label)
    return '{}'.format(id)


def git_commit_timestamp():
    root_dir = dirname(settings.BASE_DIR)
    try:
        with open(join(root_dir, 'git_commit_timestamp'), 'r') as f:
            return f.read().strip()
    except IOError:
        return ''


SESSION_CODE_CHARSET = string.ascii_lowercase + string.digits


def random_chars(num_chars):
    return ''.join(random.choice(SESSION_CODE_CHARSET) for _ in range(num_chars))


def random_chars_8():
    return random_chars(8)


def random_chars_10():
    return random_chars(10)


def app_name_format(app_name):
    app_label = app_name.split('.')[-1]
    return title(app_label.replace("_", " "))


def directory_name(path):
    return os.path.basename(os.path.normpath(path))


def get_models_module(app_name):
    module_name = '{}.models'.format(app_name)
    return import_module(module_name)


def get_bots_module(app_name):
    try:
        bots_module_name = '{}.bots'.format(app_name)
        bots_module = import_module(bots_module_name)
    except ImportError:
        bots_module_name = '{}.tests'.format(app_name)
        bots_module = import_module(bots_module_name)
    return bots_module


def get_views_module(app_name):
    module_name = '{}.views'.format(app_name)
    return import_module(module_name)


def get_app_constants(app_name):
    '''Return the ``Constants`` object of a app defined in the models.py file.

    Example::

        >>> from otree.common_internal import get_app_constants
        >>> get_app_constants('demo')
        <class demo.models.Constants at 0x7fed46bdb188>

    '''
    return get_models_module(app_name).Constants


def get_dotted_name(Cls):
    return '{}.{}'.format(Cls.__module__, Cls.__name__)


def get_app_label_from_import_path(import_path):
    '''App authors must not override AppConfig.label'''
    return import_path.split('.')[-2]


def get_app_label_from_name(app_name):
    '''App authors must not override AppConfig.label'''
    return app_name.split('.')[-1]


def get_app_name_from_label(app_label):
    '''
    >>> get_app_name_from_label('simple')
    'tests.simple'

    '''
    return apps.get_app_config(app_label).name


def expand_choice_tuples(choices):
    '''allows the programmer to define choices as a list of values rather
    than (value, display_value)

    '''
    if not choices:
        return None
    if not isinstance(choices[0], (list, tuple)):
        choices = [(value, value) for value in choices]
    return choices


def contract_choice_tuples(choices):
    '''Return only values of a choice tuple. If the choices are simple lists
    without display name the same list is returned

    '''
    if not choices:
        return None
    if not isinstance(choices[0], (list, tuple)):
        return choices
    return [value for value, _ in choices]


def min_players_multiple(players_per_group):
    ppg = players_per_group

    if isinstance(ppg, six.integer_types) and ppg >= 1:
        return ppg
    if isinstance(ppg, (list, tuple)):
        return sum(ppg)
    # else, it's probably None
    return 1


def missing_db_tables():
    """Try to execute a simple select * for every model registered
    """

    # need to normalize to lowercase because MySQL converts DB names to lower
    expected_table_names_dict = {
        Model._meta.db_table.lower(): '{}.{}'.format(Model._meta.app_label, Model.__name__)
        for Model in apps.get_models()
    }

    expected_table_names = set(expected_table_names_dict.keys())

    # again, normalize to lowercase
    actual_table_names = set(
        tn.lower() for tn in connection.introspection.table_names())

    missing_table_names = expected_table_names - actual_table_names

    # don't use the SQL table name because it could be uppercase or lowercase,
    # depending on whether it's MySQL
    return [expected_table_names_dict[missing_table]
            for missing_table in missing_table_names]


def make_hash(s):
    s += settings.SECRET_KEY
    return hashlib.sha224(s.encode()).hexdigest()[:8]


def get_admin_secret_code():
    s = settings.SECRET_KEY
    return hashlib.sha224(s.encode()).hexdigest()[:8]


def channels_create_session_group_name(pre_create_id):
    return 'wait_for_session_{}'.format(pre_create_id)


def channels_wait_page_group_name(session_pk, page_index,
                                  group_id_in_subsession=''):

    return 'wait-page-{}-page{}-{}'.format(
        session_pk, page_index, group_id_in_subsession)


def channels_group_by_arrival_time_group_name(session_pk, page_index):
    return 'group_by_arrival_time_session{}_page{}'.format(
        session_pk, page_index)


def validate_alphanumeric(identifier, identifier_description):
    if re.match(r'^[a-zA-Z0-9_]+$', identifier):
        return identifier
    raise ValueError(
        '{} "{}" can only contain letters, numbers, '
        'and underscores (_)'.format(
            identifier_description,
            identifier
        )
    )


def create_session_and_redirect(session_kwargs):
    pre_create_id = uuid.uuid4().hex
    session_kwargs['_pre_create_id'] = pre_create_id
    channels_group_name = channels_create_session_group_name(
        pre_create_id)
    channels.Channel('otree.create_session').send({
        'kwargs': session_kwargs,
        'channels_group_name': channels_group_name
    })

    wait_for_session_url = reverse(
        'WaitUntilSessionCreated', args=(pre_create_id,)
    )
    return HttpResponseRedirect(wait_for_session_url)


def ensure_superuser_exists(*args, **kwargs):
    """
    Creates our default superuser, returns True for success
    and False for failure
    """
    from django.contrib.auth.models import User
    username = settings.ADMIN_USERNAME
    password = settings.ADMIN_PASSWORD
    logger = logging.getLogger('otree')
    if User.objects.filter(username=username).exists():
        # msg = 'Default superuser exists.'
        # logger.info(msg)
        return True
    if not password:
        return False
    assert User.objects.create_superuser(username, email='',
                                         password=password)
    msg = 'Created superuser "{}"'.format(username)
    logger.info(msg)
    return True


def release_any_stale_locks():
    '''
    Need to release locks in case the server was stopped abruptly,
    and the 'finally' block in each lock did not execute
    '''
    from otree.models_concrete import GlobalLockModel, ParticipantLockModel
    for LockModel in [GlobalLockModel, ParticipantLockModel]:
        try:
            LockModel.objects.filter(locked=True).update(locked=False)
        except:
            # if server is started before DB is synced,
            # this will raise
            # django.db.utils.OperationalError: no such table:
            # otree_globallockmodel
            # we can ignore that because we just want to make sure there are no
            # active locks
            pass


def get_redis_conn():
    '''reuse Huey Redis connection'''
    return HUEY.storage.conn

def has_group_by_arrival_time(app_name):
    page_sequence = get_views_module(app_name).page_sequence
    if len(page_sequence) == 0:
        return False
    return getattr(page_sequence[0], 'group_by_arrival_time', False)


@contextlib.contextmanager
def transaction_except_for_sqlite():
    '''
    On SQLite, transactions tend to result in "database locked" errors.
    So, skip the transaction on SQLite, to allow local dev.
    Should only be used if omitting the transaction rarely causes problems.
    '''
    if settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
        yield
    else:
        with transaction.atomic():
            yield


class DebugTable(object):
    def __init__(self, title, rows):
        self.title = title
        self.rows = []
        for k, v in rows:
            if isinstance(v, six.string_types):
                v = v.strip().replace("\n", "<br>")
                v = mark_safe(v)
            self.rows.append((k, v))