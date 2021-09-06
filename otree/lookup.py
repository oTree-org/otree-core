from collections import namedtuple
from functools import lru_cache
from typing import Dict

from otree.common import get_pages_module, get_models_module, get_constants
from otree.database import dbq
from otree.models import Session

PageLookup = namedtuple(
    'PageInfo',
    [
        'app_name',
        'page_class',
        'round_number',
        'subsession_id',
        'name_in_url',
        'session_pk',
    ],
)


@lru_cache(maxsize=32)
def _get_session_lookups(session_code) -> Dict[int, PageLookup]:
    session = dbq(Session).filter_by(code=session_code).one()
    pages = {}
    idx = 1
    for app_name in session.config['app_sequence']:
        models = get_models_module(app_name)
        Subsession = models.Subsession
        page_sequence = get_pages_module(app_name).page_sequence
        subsessions = {
            s[0]: s[1]
            for s in Subsession.objects_filter(session=session).with_entities(
                Subsession.round_number, Subsession.id
            )
        }

        Constants = get_constants(app_name)
        num_rounds = Constants.get_normalized('num_rounds')
        name_in_url = Constants.get_normalized('name_in_url')
        for rd in range(1, num_rounds + 1):
            for PageClass in page_sequence:
                pages[idx] = PageLookup(
                    app_name=app_name,
                    page_class=PageClass,
                    round_number=rd,
                    subsession_id=subsessions[rd],
                    session_pk=session.id,
                    name_in_url=name_in_url,
                )
                idx += 1
    return pages


def get_page_lookup(session_code, idx) -> PageLookup:
    cache = _get_session_lookups(session_code)
    return cache[idx]


def get_min_idx_for_app(session_code, app_name):
    '''for aatp'''
    for idx, info in _get_session_lookups(session_code).items():
        if info.app_name == app_name:
            return idx


def url_i_should_be_on(participant_code, session_code, index_in_pages) -> str:
    idx = index_in_pages
    lookup = get_page_lookup(session_code, idx)
    return lookup.page_class.get_url(
        participant_code=participant_code,
        name_in_url=lookup.name_in_url,
        page_index=idx,
    )
