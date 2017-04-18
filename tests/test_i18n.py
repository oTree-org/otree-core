#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .base import TestCase
from otree.session import create_session
from otree.bots.bot import ParticipantBot
from .base import TestCase
import mock
from otree.models.session import Session
from otree.bots.runner import session_bot_runner_factory
from django.test import override_settings

class TestI18N(TestCase):
    def setUp(self):
        session = create_session('i18n', num_participants=1, use_cli_bots=True)
        self.bot_runner = session_bot_runner_factory(session)

    @override_settings(LANGUAGE_CODE='de')
    def test_german(self):
        self.bot_runner.play()

    @override_settings(LANGUAGE_CODE='zh-hans')
    def test_chinese(self):
        self.bot_runner.play()
