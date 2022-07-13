import asyncio
import hashlib
import itertools
import os
from random import Random
import re
import string
import sys
import urllib.parse
from collections import OrderedDict
from importlib import import_module
from typing import Iterable, Tuple
from pathlib import Path
from functools import lru_cache

from itsdangerous import Signer

from otree import settings

# set to False if using runserver

USE_TIMEOUT_WORKER = bool(os.getenv('USE_TIMEOUT_WORKER'))

# use a separate rng instance to avoid issues when another app
# sets random.seed(),
# for example every session getting the same code.
rng = Random()


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
    return ''.join(rng.choice(SESSION_CODE_CHARSET) for _ in range(num_chars))


def random_chars_8():
    return random_chars(8)


CONSONANTS = 'bdfghjklmnprstvz'
VOWELS = 'aeiou'

SYLLABLES = [c + v for c in CONSONANTS for v in VOWELS]


def random_chars_join_code():
    return ''.join(rng.sample(SYLLABLES, 4))


@lru_cache()
def is_noself(app_name):
    init_path = Path(f'{app_name}/__init__.py')
    return init_path.exists() and 'import' in init_path.read_text('utf8')


def get_bots_module(app_name):
    return import_module(f'{app_name}.tests')


@lru_cache()
def get_models_module(app_name):
    module_name = app_name if is_noself(app_name) else f'{app_name}.models'
    return import_module(module_name)


@lru_cache()
def get_pages_module(app_name):
    module_name = [f'{app_name}.pages', app_name][is_noself(app_name)]

    try:
        return import_module(module_name)
    except Exception as exc:
        # to give a smaller traceback on startup
        import traceback

        traceback.print_exc()
        sys.exit(1)


@lru_cache()
def get_constants(app_name):
    models = get_models_module(app_name)
    if hasattr(models, 'Constants'):
        return models.Constants
    return models.C


def get_builtin_constant(app_name, constant_name):
    Constants = get_constants(app_name)
    return Constants.get_normalized(constant_name)


def get_dotted_name(Cls):
    return '{}.{}'.format(Cls.__module__, Cls.__name__)


def get_app_label_from_import_path(import_path):
    """works for self and no-self"""
    return import_path.split('.')[0]


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


ADMIN_SECRET_CODE = get_admin_secret_code()
DATA_EXPORT_HASH = make_hash('dataexport')

_signer = Signer(_SECRET)


def signer_sign(s):
    return _signer.sign(s).decode('utf8')


def signer_unsign(sh):
    return _signer.unsign(sh.encode('utf8')).decode('utf8')


def validate_alphanumeric(identifier, identifier_description):
    if re.match(r'^[a-zA-Z0-9_]+$', identifier):
        return identifier
    msg = '{} "{}" can only contain letters, numbers, ' 'and underscores (_)'.format(
        identifier_description, identifier
    )
    raise ValueError(msg)


def has_group_by_arrival_time(app_name):
    page_sequence = get_pages_module(app_name).page_sequence
    return bool(page_sequence) and getattr(
        page_sequence[0], 'group_by_arrival_time', False
    )


class DebugTable:
    def __init__(self, title, rows: Iterable[Tuple]):
        self.title = title
        self.rows = []
        for k, v in rows:
            if isinstance(v, str):
                v = v.strip().replace("\n", "<br>")
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
            rng.shuffle(column)
        return list(zip(*group_matrix))
    else:
        rng.shuffle(players)
        return _group_by_rank(players, players_per_group)


class GlobalState:
    browser_bots_launcher_session_code = ''


NON_FIELD_ERROR_KEY = '__all__'
CSRF_TOKEN_NAME = 'csrftoken'
AUTH_COOKIE_NAME = 'otreeadminauth'
AUTH_COOKIE_VALUE = signer_sign(AUTH_COOKIE_NAME)


lock = asyncio.Lock()


class FULL_DECIMAL_PLACES:
    pass


def get_class_bounds(txt, ClassName):
    class_start = txt.index(f'\nclass {ClassName}(')
    m = list(re.finditer(r'^\w', txt[class_start:], re.MULTILINE))[1]
    class_end = class_start + m.start()
    return class_start, class_end


def app_name_validity_message(name):
    if not name.isidentifier():
        return (
            f"'{name}' is not a valid name. Please make sure the "
            "name is a valid Python identifier."
        )
    max_chars = 40
    if len(name) > max_chars:
        return f"Name must be shorter than {max_chars} characters"
