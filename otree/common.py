import contextlib
import hashlib
import importlib.util
import sys
import sqlite3
import itertools
import logging
import random
import re
import string
from collections import OrderedDict
from importlib import import_module
from pathlib import Path
from typing import Iterable, Tuple
from django.apps import apps
from django.db import connection
from django.db import transaction
import urllib
import os
import json
from django.conf import settings
from django.utils.safestring import mark_safe

# until 2016, otree apps imported currency from otree.common.
from otree.currency import Currency, RealWorldCurrency, currency_range  # noqa

# set to False if using runserver

USE_TIMEOUT_WORKER = bool(os.getenv('USE_TIMEOUT_WORKER'))


class _CurrencyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (Currency, RealWorldCurrency)):
            if obj.get_num_decimal_places() == 0:
                return int(obj)
            return float(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


def json_dumps(obj):
    return json.dumps(obj, cls=_CurrencyEncoder)


def safe_json(obj):
    return mark_safe(json_dumps(obj))


def add_params_to_url(url, params):
    url_parts = list(urllib.parse.urlparse(url))

    # use OrderedDict because sometimes we want certain params at end
    # for readability/consistency
    query = OrderedDict(urllib.parse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urllib.parse.urlencode(query)
    return urllib.parse.urlunparse(url_parts)


SESSION_CODE_CHARSET = string.ascii_lowercase + string.digits


def random_chars(num_chars):
    return ''.join(random.choice(SESSION_CODE_CHARSET) for _ in range(num_chars))


def random_chars_8():
    return random_chars(8)


def random_chars_10():
    return random_chars(10)


def get_models_module(app_name):
    '''shouldn't rely on app registry because the app might have been removed
    from SESSION_CONFIGS, especially if the session was created a long time
    ago and you want to export it'''
    return import_module(f'{app_name}.models')


def get_bots_module(app_name):
    return import_module(f'{app_name}.tests')


def get_pages_module(app_name):
    '''views.py is deprecated, remove it soon'''
    for module_name in ['pages', 'views']:
        dotted = '{}.{}'.format(app_name, module_name)
        if importlib.util.find_spec(dotted):
            return import_module(dotted)
    msg = 'No pages module found for app {}'.format(app_name)
    raise ImportError(msg)


def get_app_constants(app_name):
    return get_models_module(app_name).Constants


def get_dotted_name(Cls):
    return '{}.{}'.format(Cls.__module__, Cls.__name__)


def get_app_label_from_import_path(import_path):
    '''App authors must not override AppConfig.label'''
    return import_path.split('.')[-2]


def get_app_label_from_name(app_name):
    '''App authors must not override AppConfig.label'''
    return app_name.split('.')[-1]


def expand_choice_tuples(choices):
    '''allows the programmer to define choices as a list of values rather
    than (value, display_value)

    '''
    if not choices:
        return None
    if not isinstance(choices[0], (list, tuple)):
        choices = [(value, value) for value in choices]
    return choices


def missing_db_tables():
    """Try to execute a simple select * for every model registered
    """

    # need to normalize to lowercase because MySQL converts DB names to lower
    expected_table_names_dict = {
        Model._meta.db_table.lower(): '{}.{}'.format(
            Model._meta.app_label, Model.__name__
        )
        for Model in apps.get_models()
    }

    expected_table_names = set(expected_table_names_dict.keys())

    # again, normalize to lowercase
    actual_table_names = set(
        tn.lower() for tn in connection.introspection.table_names()
    )

    missing_table_names = expected_table_names - actual_table_names

    # don't use the SQL table name because it could be uppercase or lowercase,
    # depending on whether it's MySQL
    return [
        expected_table_names_dict[missing_table]
        for missing_table in missing_table_names
    ]


def make_hash(s):
    s += settings.SECRET_KEY
    return hashlib.sha224(s.encode()).hexdigest()[:8]


def get_admin_secret_code():
    s = settings.SECRET_KEY
    return hashlib.sha224(s.encode()).hexdigest()[:8]


def validate_alphanumeric(identifier, identifier_description):
    if re.match(r'^[a-zA-Z0-9_]+$', identifier):
        return identifier
    msg = '{} "{}" can only contain letters, numbers, ' 'and underscores (_)'.format(
        identifier_description, identifier
    )
    raise ValueError(msg)


EMPTY_ADMIN_USERNAME_MSG = 'ADMIN_USERNAME is undefined'
EMPTY_ADMIN_PASSWORD_MSG = 'ADMIN_PASSWORD is undefined'


def ensure_superuser_exists(*args, **kwargs) -> str:
    """
    Creates our default superuser.
    If it fails, it returns a failure message
    The weakness of this is that if you change your password, you need to resetdb.
    but that doesn't affect many people. we could show a warning saying that
    ADMIN_PASSWORD doesn't match the hashed password, but i could not find a trivial way
    to do that. the make_password function is nondeterministic.
    """
    username = settings.ADMIN_USERNAME
    password = settings.ADMIN_PASSWORD
    if not username:
        return EMPTY_ADMIN_USERNAME_MSG
    if not password:
        return EMPTY_ADMIN_PASSWORD_MSG
    from django.contrib.auth.models import User

    if User.objects.filter(username=username).exists():
        return ''
    User.objects.create_superuser(username, email='', password=password)
    msg = 'Created superuser "{}"'.format(username)
    logging.getLogger('otree').info(msg)
    return ''


def has_group_by_arrival_time(app_name):
    page_sequence = get_pages_module(app_name).page_sequence
    if len(page_sequence) == 0:
        return False
    # it might not be a waitpage
    return getattr(page_sequence[0], 'group_by_arrival_time', False)


def is_sqlite():
    return settings.DATABASES['default']['ENGINE'].endswith('sqlite3')


@contextlib.contextmanager
def transaction_except_for_sqlite():
    '''
    On SQLite, transactions tend to result in "database locked" errors.
    So, skip the transaction on SQLite, to allow local dev.
    Should only be used if omitting the transaction rarely causes problems.
    2020-10-13: maybe not needed now that we are single threaded
    '''
    if is_sqlite():
        yield
    else:
        with transaction.atomic():
            yield


class DebugTable:
    def __init__(self, title, rows: Iterable[Tuple]):
        self.title = title
        self.rows = []
        for k, v in rows:
            if isinstance(v, str):
                v = v.strip().replace("\n", "<br>")
                v = mark_safe(v)
            self.rows.append((k, v))


class InvalidRoundError(ValueError):
    pass


def in_round(ModelClass, round_number, **kwargs):
    if round_number < 1:
        msg = 'Invalid round number: {}'.format(round_number)
        raise InvalidRoundError(msg)
    try:
        return ModelClass.objects.get(round_number=round_number, **kwargs)
    except ModelClass.DoesNotExist:
        msg = 'No corresponding {} found with round_number={}'.format(
            ModelClass.__name__, round_number
        )
        raise InvalidRoundError(msg) from None


def in_rounds(ModelClass, first, last, **kwargs):
    if first < 1:
        msg = 'Invalid round number: {}'.format(first)
        raise InvalidRoundError(msg)
    qs = ModelClass.objects.filter(
        round_number__range=(first, last), **kwargs
    ).order_by('round_number')

    ret = list(qs)
    num_results = len(ret)
    expected_num_results = last - first + 1
    if num_results != expected_num_results:
        msg = 'Database contains {} records for rounds {}-{}, but expected {}'.format(
            num_results, first, last, expected_num_results
        )
        raise InvalidRoundError(msg)
    return ret


class BotError(AssertionError):
    pass


def _get_all_configs():
    return [
        app
        for app in apps.get_app_configs()
        if app.name in settings.INSTALLED_OTREE_APPS
    ]


def participant_start_url(code):
    return '/InitializeParticipant/{}'.format(code)


def patch_migrations_module():
    from django.db.migrations.loader import MigrationLoader

    def migrations_module(*args, **kwargs):
        # need to return None so that load_disk() considers it
        # unmigrated, and False so that load_disk() considers it
        # non-explicit
        return None, False

    MigrationLoader.migrations_module = migrations_module


class ResponseForException(Exception):
    '''
    allows us to show a much simplified traceback without
    framework code.
    '''

    pass


def _group_by_rank(ranked_list, players_per_group):
    ppg = players_per_group
    players = ranked_list
    group_matrix = []
    for i in range(0, len(players), ppg):
        group_matrix.append(players[i : i + ppg])
    return group_matrix


def _group_randomly(group_matrix, fixed_id_in_group=False):
    """Random Uniform distribution of players in every group"""

    players = list(itertools.chain.from_iterable(group_matrix))
    sizes = [len(group) for group in group_matrix]
    if sizes and any(size != sizes[0] for size in sizes):
        raise ValueError('This algorithm does not work with unevenly sized groups')
    players_per_group = sizes[0]

    if fixed_id_in_group:
        group_matrix = [list(col) for col in zip(*group_matrix)]
        for column in group_matrix:
            random.shuffle(column)
        return list(zip(*group_matrix))
    else:
        random.shuffle(players)
        return _group_by_rank(players, players_per_group)


_dumped = False


def dump_db_and_exit(*args, code=0):
    # https://stackoverflow.com/a/17729312/10460916

    global _dumped
    if _dumped:
        return

    dump_db()

    sys.exit(code)


def dump_db(*args):

    # return
    global _dumped
    if _dumped:
        return
    from django.db import connection

    dest = sqlite3.connect('db.sqlite3')
    # when i called dump_db() from a view, the connection was None
    # until I made a query
    from otree.models import Session

    try:
        Session.objects.first()
    except Exception as exc:
        # if dump_db is called before migrate is finished, we get:
        # OperationalError: no such table: otree_session
        return
    connection.connection.backup(dest)
    _dumped = True
    sys.stdout.write('Database saved\n')


class NoOp:
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def load_db():
    db_path = Path('db.sqlite3')
    if db_path.exists():
        from django.db import connection

        src = sqlite3.connect('db.sqlite3')
        src.backup(connection.connection)
    else:
        sys.stdout.write('Creating new database\n')
