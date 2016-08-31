#!/usr/bin/env python
# -*- coding: utf-8 -*-

from six import StringIO

from django.conf import settings
from django.core.management import call_command

from otree import common_internal
from otree.session import SESSION_CONFIGS_DICT

from .base import TestCase


class TestDataExport(TestCase):
    def setUp(self):
        self.client.login()

    def test_export(self):

        session_config_name = 'export'
        app_name = 'tests.export'
        num_participants = 2

        call_command('create_session', session_config_name,
                     str(num_participants))

        formatted_app_name = common_internal.app_name_format(app_name)

        url = "/ExportCsv/{}/".format(app_name)
        response = self.client.get(url)

        # HEADERS CHECK
        content_disposition = response["Content-Disposition"]
        content_type = response["content-type"]

        self.assertEqual(content_type, "text/csv")

        self.assertTrue(
            content_disposition.startswith(
                'attachment; filename="{} ('.format(formatted_app_name)))

        csv_text = response.content.decode('utf-8')

        rows = csv_text.split('\n')

        # 1 row for each player + header row + blank row at end
        self.assertEqual(len(rows), num_participants + 2)

        header_row = rows[0]

        for expected_text in [
            'Participant.id_in_session',
            'Player.id_in_group',
            'Player.payoff',
            'Group.group_field',
            'Subsession.subsession_field',
            'Subsession.round_number',
            'Session.code',
        ]:
            self.assertIn(expected_text, header_row)

        # 3.14 should be in the CSV without any currency formatting
        for expected_text in ['should be in export CSV', ',3.14,']:
            self.assertIn(expected_text, csv_text)

        # True/False should be converted to 1/0
        self.assertNotIn('False', csv_text)


class TestDocExport(TestCase):
    def setUp(self):
        self.client.login()

    def session_test(self, session_name):
        session_conf = SESSION_CONFIGS_DICT[session_name]
        app_sequence = session_conf["app_sequence"]
        npar = session_conf["num_demo_participants"]

        call_command('create_session', session_name, str(npar))

        for app in app_sequence:
            app_format = common_internal.app_name_format(app)

            url = "/ExportAppDocs/{}/".format(app)
            response = self.client.get(url)

            # HEADERS CHECK
            content_disposition = response["Content-Disposition"]
            content_type = response["content-type"]

            self.assertEqual(content_type, "text/plain")

            expected_cd = 'attachment; filename="{} - documentation ('.format(
                app_format)
            self.assertTrue(content_disposition.startswith(expected_cd))

            buff = StringIO()
            common_internal.export_docs(buff, app)
            self.assertEqual(response.content, buff.getvalue().encode('utf-8'))

    def test_simple_game_export_data(self):
        self.session_test("simple")

    def test_misc_1p_game_export_docs(self):
        self.session_test("misc_1p")

    def test_misc_3p_game_export_docs(self):
        self.session_test("misc_3p")

    def test_two_simple_games_export_docs(self):
        self.session_test("two_simple_games")


class TestTimeSpentExport(TestCase):
    def setUp(self):
        for session_conf in settings.SESSION_CONFIGS:
            session_name = session_conf["name"]
            npar = session_conf["num_demo_participants"]
            call_command('create_session', session_name, str(npar))
        self.client.login()

    def test_time_spent(self):
        response = self.client.get("/ExportTimeSpent/")

        # HEADERS CHECK
        content_type = response["content-type"]
        self.assertEqual(content_type, "text/csv")

        buff = StringIO()
        common_internal.export_time_spent(buff)
        self.assertEqual(response.content, buff.getvalue().encode('utf-8'))
