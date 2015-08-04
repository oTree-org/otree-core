#!/usr/bin/env python
# -*- coding: utf-8 -*-

import six

from django.conf import settings
from django.core.management import call_command

from otree import common_internal

from .base import TestCase


class TestDataExport(TestCase):

    def setUp(self):
        self.client.login()

    def get_session_conf(self, session_name):
        for current_session_conf in settings.SESSION_CONFIGS:
            if current_session_conf["name"] == session_name:
                return current_session_conf

    def session_test(self, session_name):

        session_conf = self.get_session_conf(session_name)
        app_sequence = session_conf["app_sequence"]
        npar = session_conf["num_demo_participants"]

        call_command('create_session', session_name, str(npar))

        for app in app_sequence:
            app_format = common_internal.app_name_format(app)

            url = "/ExportCsv/{}/".format(app)
            response = self.client.get(url)

            # HEADERS CHECK
            content_disposition = response["Content-Disposition"]
            content_type = response["content-type"]

            self.assertEqual(content_type, "text/csv")

            self.assertTrue(
                content_disposition.startswith(
                    'attachment; filename="{} ('.format(app_format)))

            buff = six.StringIO()
            common_internal.export_data(buff, app)
            self.assertEqual(response.content, buff.getvalue())

    def test_simple_game_export_data(self):
        self.session_test("simple_game")

    def test_single_player_game_export_data(self):
        self.session_test("single_player_game")

    def test_multi_player_game_export_data(self):
        self.session_test("multi_player_game")

    def test_two_simple_games_export_data(self):
        self.session_test("two_simple_games")
