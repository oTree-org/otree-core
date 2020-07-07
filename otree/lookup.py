from functools import lru_cache
from typing import Dict, Tuple
from otree.models import Session
from collections import namedtuple
from otree.common import get_pages_module, get_models_module

PageLookup = namedtuple(
    'PageInfo',
    [
        'app_name',
        'page_class',
        'round_number',
        'subsession_id',
        'name_in_url',
        'session_pk',
        'is_first_in_round',
    ],
)


@lru_cache(maxsize=32)
def _get_session_lookups(session_code) -> Dict[int, PageLookup]:
    session = Session.objects.get(code=session_code)
    pages = {}
    idx = 1
    for app_name in session.config['app_sequence']:
        models = get_models_module(app_name)
        page_sequence = get_pages_module(app_name).page_sequence
        subsessions = {
            s['round_number']: s['id']
            for s in models.Subsession.objects.filter(session=session).values(
                'id', 'round_number'
            )
        }

        for rd in range(1, models.Constants.num_rounds + 1):
            is_first_in_round = True
            for PageClass in page_sequence:
                pages[idx] = PageLookup(
                    app_name=app_name,
                    page_class=PageClass,
                    round_number=rd,
                    subsession_id=subsessions[rd],
                    # TODO: remove session ID, just use code everywhere
                    session_pk=session.pk,
                    name_in_url=models.Constants.name_in_url,
                    is_first_in_round=is_first_in_round,
                )
                is_first_in_round = False
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

