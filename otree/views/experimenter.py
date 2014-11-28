import vanilla
from otree import constants

import django.test

def advance_last_place_players(session):
    participants = session.get_participants()

    # what about people who haven't started?

    last_place_subsession_index = min([p._index_in_subsessions for p in participants])
    last_place_subsession_players = [p._current_user() for p in participants if p._index_in_subsessions == last_place_subsession_index]

    last_place_page_index = min([p.index_in_pages for p in last_place_subsession_players])
    last_place_players = [p for p in last_place_subsession_players if p.index_in_pages == last_place_page_index]

    last_place_participants = [p.participant for p in last_place_players]

    c = django.test.Client()

    for p in last_place_participants:
        c.post(p.current_page_url, data={constants.auto_submit: True}, follow=True)


