#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.management import call_command
from otree.models.session import Session
from otree.bots.bot import ParticipantBot
from .base import TestCase
import mock
import tests.wait_page.views


class TestWaitForAllGroups(TestCase):
    def setUp(self):
        call_command('create_session', 'wait_page', "4")
        session = Session.objects.get()
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
