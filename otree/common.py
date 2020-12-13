import asyncio
import hashlib
import sys
import itertools
import json
import os
import random
import re
import string
import urllib.parse
from collections import OrderedDict
from importlib import import_module
from typing import Iterable, Tuple

from otree import settings

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
    # todo: mark_safe
    return json_dumps(obj)


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
    try:
        return import_module(f'{app_name}.pages')
    except Exception as exc:
        # to give a smaller traceback on startup
        import traceback

        traceback.print_exc()
        sys.exit(1)


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


_SECRET = settings.SECRET_KEY + (settings.ADMIN_PASSWORD or '')


def make_hash(s):
    s += _SECRET
    return hashlib.sha224(s.encode()).hexdigest()[:8]


def get_admin_secret_code():
    s = _SECRET
    return hashlib.sha224(s.encode()).hexdigest()[:8]


# TODO: use itsdangerous instead
def signer_sign(s, sep=':'):
    return s + sep + make_hash(s)[:8]


def signer_unsign(sh, sep=':'):
    s, _ = sh.rsplit(sep, maxsplit=1)
    if sh != signer_sign(s, sep=sep):
        raise ValueError(f'bad signature: {sh}')
    return s


def validate_alphanumeric(identifier, identifier_description):
    if re.match(r'^[a-zA-Z0-9_]+$', identifier):
        return identifier
    msg = '{} "{}" can only contain letters, numbers, ' 'and underscores (_)'.format(
        identifier_description, identifier
    )
    raise ValueError(msg)


def has_group_by_arrival_time(app_name):
    page_sequence = get_pages_module(app_name).page_sequence
    if len(page_sequence) == 0:
        return False
    # it might not be a waitpage
    return getattr(page_sequence[0], 'group_by_arrival_time', False)


def is_sqlite():
    return settings.DATABASES['default']['ENGINE'].endswith('sqlite3')


class DebugTable:
    def __init__(self, title, rows: Iterable[Tuple]):
        self.title = title
        self.rows = []
        for k, v in rows:
            if isinstance(v, str):
                v = v.strip().replace("\n", "<br>")
                # TODO:
                # v = mark_safe(v)
            self.rows.append((k, v))


class InvalidRoundError(ValueError):
    pass


def in_round(ModelClass, round_number, **kwargs):
    if round_number < 1:
        msg = 'Invalid round number: {}'.format(round_number)
        raise InvalidRoundError(msg)
    try:
        return ModelClass.objects_filter(round_number=round_number, **kwargs).one()
    except Exception as exc:
        from otree.database import NoResultFound

        if isinstance(exc, NoResultFound):
            msg = 'No corresponding {} found with round_number={}'.format(
                ModelClass.__name__, round_number
            )
            raise InvalidRoundError(msg) from None
        raise


def in_rounds(ModelClass, first, last, **kwargs):
    if first < 1:
        msg = 'Invalid round number: {}'.format(first)
        raise InvalidRoundError(msg)
    ret = list(
        ModelClass.objects_filter(
            ModelClass.round_number >= first, ModelClass.round_number <= last, **kwargs
        ).order_by('round_number')
    )
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


def participant_start_url(code):
    return '/InitializeParticipant/{}'.format(code)


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


class GlobalState:
    browser_bots_launcher_session_code = ''


NON_FIELD_ERROR_KEY = None
CSRF_TOKEN_NAME = 'csrftoken'
AUTH_COOKIE_NAME = 'otreeadminauth'
AUTH_COOKIE_VALUE = make_hash('otreeadminauth')


lock = asyncio.Lock()
