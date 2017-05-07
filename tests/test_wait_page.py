#!/usr/bin/env python
# -*- coding: utf-8 -*-

from otree.session import create_session
from otree.models.session import Session
from otree.bots.bot import ParticipantBot
from .base import TestCase
from unittest import mock
import tests.wait_page.views


class TestWaitForAllGroups(TestCase):
    def setUp(self):
        session = create_session(
            'wait_page', num_participants=4, use_cli_bots=True)
        subsession = session.get_subsessions()[0]
        self.group1 = subsession.get_groups()[0]

    def start_some_players(self, should_be_stuck):
        bots = []
        for player in self.group1.get_players():
            bot = ParticipantBot(player.participant, load_player_bots=False)
            bots.append(bot)
        for bot in bots:
            bot.open_start_url()
        for bot in bots:
            bot.open_start_url()
            self.assertEqual(bot.on_wait_page(), should_be_stuck)

    def test_dont_wait_for_all(self):
        self.start_some_players(should_be_stuck=False)

    def test_wait_for_all_groups(self):
        with mock.patch.object(
                tests.wait_page.views.MyWait,
                'wait_for_all_groups',
                new_callable=mock.PropertyMock,
                return_value=True):
            self.start_some_players(should_be_stuck=True)


class TestSkipWaitPage(TestCase):
    def setUp(self):
        session = create_session(
            'skip_wait_page', num_participants=2, use_cli_bots=True)
        bots = []
        for participant in session.get_participants():
            bot = ParticipantBot(participant, load_player_bots=False)
            bots.append(bot)
        self.bots = bots

    def visit(self, ordered_bots):
        for bot in ordered_bots:
            bot.open_start_url()
        for bot in ordered_bots:
            bot.open_start_url()
            self.assertFalse(bot.on_wait_page())

    def test_skipper_visits_last(self):
        self.visit(self.bots)

    def test_waiter_visits_last(self):
        self.visit(reversed(self.bots))
