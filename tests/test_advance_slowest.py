#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.management import call_command
from otree.models.session import Session
from otree.bots.bot import ParticipantBot
from .base import TestCase


# use a wrapper so that unittest doesn't find this base class at the
# module level, otherwise it will run it.
class WrapperToHideClass:
    class BaseTestCase(TestCase):

        def advance_to_end(self):

            session = self.session
            participants = session.get_participants()
            max_page_index = participants[0]._max_page_index

            # once to open the start links, then num_pages to get to last page
            for x in range(max_page_index + 1):
                session.advance_last_place_participants()

            participants = session.get_participants()
            for p in participants:
                self.assertGreaterEqual(p._index_in_pages, max_page_index)

        def test_advance_to_end(self):
            self.advance_to_end()

        def test_some_already_started(self):
            participants = self.session.get_participants()
            p1 = participants[0]

            bot = ParticipantBot(p1, load_player_bots=False)
            bot.open_start_url()
            self.advance_to_end()


class TestAdvanceSlowest(WrapperToHideClass.BaseTestCase):
    def setUp(self):
        call_command('create_session', 'advance_slowest', "2")
        self.session = Session.objects.get()


class TestAdvanceSlowestWaitPageFirst(WrapperToHideClass.BaseTestCase):
    def setUp(self):
        call_command('create_session', 'advance_slowest_wait', "2")
        self.session = Session.objects.get()
