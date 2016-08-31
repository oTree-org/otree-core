#!/usr/bin/env python
# -*- coding: utf-8 -*-

from otree.bots.bot import ParticipantBot
from .base import TestCase
import otree.session
from otree.bots.runner import SessionBotRunner
import logging


class TestBots(TestCase):
    def test_bot_runs(self):

        session = otree.session.create_session(
            session_config_name='bots',
            num_participants=2,
            use_cli_bots=True,
            bot_case_number=0,
        )

        bots = []
        for participant in session.get_participants():
            bot = ParticipantBot(participant)
            bots.append(bot)
            bot.open_start_url()

        bot_runner = SessionBotRunner(bots, session.code)

        with self.assertRaises(ZeroDivisionError):
            bot_runner.play_until_end()

    def test_bots_check_html(self):

        session = otree.session.create_session(
            session_config_name='bots_check_html',
            num_participants=1,
            use_cli_bots=True,
            bot_case_number=0,
        )

        bots = []

        with self.settings(BOTS_CHECK_HTML=True):
            from django.conf import settings
            self.assertEqual(settings.BOTS_CHECK_HTML, True)
            for participant in session.get_participants():
                bot = ParticipantBot(participant)
                bots.append(bot)
                bot.open_start_url()

            bot_runner = SessionBotRunner(bots, session.code)

            try:
                bot_runner.play_until_end()
            except AssertionError as exc:
                # AssertionError should say something about check_html
                raises_correct_message = 'check_html' in str(exc)
            else:
                raises_correct_message = False
            if not raises_correct_message:
                raise AssertionError('bots check_html not working properly')

    def test_bot_bad_post(self):
        """
        Test that posting bad data without using SubmitInvalid
        will raise an error.
        """

        session = otree.session.create_session(
            session_config_name='bots_bad_post',
            num_participants=1,
            use_cli_bots=True,
            bot_case_number=0,
        )

        bots = []
        for participant in session.get_participants():
            bot = ParticipantBot(participant)
            bots.append(bot)
            bot.open_start_url()

        bot_runner = SessionBotRunner(bots, session.code)

        with self.assertRaises(AssertionError):
            # need to disable log output, because this triggers an exception
            # that is logged to stdout
            logging.disable(logging.CRITICAL)
            bot_runner.play_until_end()
            logging.disable(logging.NOTSET)
