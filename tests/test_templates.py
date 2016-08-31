#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.management import call_command
import otree.session
from otree.bots.bot import ParticipantBot
from .base import TestCase
import mock


class TestTemplates(TestCase):
    def test_all_blocks_found(self):
        session = otree.session.create_session(
            session_config_name='templates_app',
            num_participants=1,
            use_cli_bots=True,
            bot_case_number=0,
        )

        participant = session.get_participants()[0]
        bot = ParticipantBot(participant, load_player_bots=False)
        bot.open_start_url()
        for block_name in [
            'scripts', 'app_scripts', 'global_scripts',
            'styles', 'app_styles', 'global_styles',
        ]:
            self.assertIn('my_{}'.format(block_name), bot.html)
