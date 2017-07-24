from six import StringIO

from django.conf import settings
from django.core.management import call_command

from otree import common_internal
import otree.export
from otree.session import SESSION_CONFIGS_DICT
import re
from .base import TestCase
import otree.session
from tests.export.models import Constants

class TestDataExport(TestCase):
    def setUp(self):
        self.client.login()

    def test_export(self):

        session_config_name = 'export'
        app_name = 'tests.export'
        num_participants = 3
        num_sessions = 2

        # 3 sessions, 3 participants each is good to test alignment
        for i in range(num_sessions):
            otree.session.create_session(
                session_config_name=session_config_name,
                num_participants=num_participants,
            )

        url = "/ExportApp/{}/".format(app_name)
        response = self.client.get(url)

        # HEADERS CHECK
        content_disposition = response["Content-Disposition"]
        content_type = response["content-type"]

        self.assertEqual(content_type, "text/csv")

        self.assertTrue(
            content_disposition.startswith(
                'attachment; filename='))

        csv_text = response.content.decode('utf-8')

        rows = [row for row in csv_text.split('\n') if row.strip()]

        # 1 row for each player + header row
        self.assertEqual(
            len(rows),
            num_sessions * num_participants * Constants.num_rounds + 1)

        header_row = rows[0]

        for expected_text in [
            'participant.id_in_session',
            'player.id_in_group',
            'player.payoff',
            'group.group_field',
            'subsession.subsession_field',
            'subsession.round_number',
            'session.code',
        ]:
            self.assertIn(expected_text, header_row)

        # 3.14 should be in the CSV without any currency formatting
        for expected_text in ['should be in export CSV', ',3.14,']:
            self.assertIn(expected_text, csv_text)

        # True/False should be converted to 1/0
        self.assertNotIn('False', csv_text)

        # test alignment
        for row in rows[1:]:
            participant_code = re.search(',ALIGN_TO_PARTICIPANT_(\w+),', row).group(1)
            self.assertIn(r',{},'.format(participant_code), row)

            session_code = re.search(',ALIGN_TO_SESSION_(\w+),', row).group(1)
            self.assertIn(',{},'.format(session_code), row)

            group_id = re.search(',GROUP_(\d+),', row).group(1)
            self.assertIn(',ALIGN_TO_GROUP_{},'.format(group_id), row)

            subsession_id = re.search(',SUBSESSION_(\d+),', row).group(1)
            self.assertIn(',ALIGN_TO_SUBSESSION_{},'.format(subsession_id), row)


class TestWideCSV(TestCase):

    def test_export(self):

        session_config_name = 'export'
        app_name = 'tests.export'
        num_participants = 3
        num_sessions = 3

        # 3 sessions, 3 participants each is good to test alignment
        for i in range(num_sessions):
            otree.session.create_session(
                session_config_name=session_config_name,
                num_participants=num_participants,
            )

        with StringIO() as f:
            otree.export.export_wide(f, file_extension='csv')
            csv_text = f.getvalue()

        rows = [row for row in csv_text.split('\n') if row.strip()]

        # 1 row for each player + header row
        self.assertEqual(len(rows), num_participants * num_sessions + 1)

        header_row = rows[0]

        for expected_text in [
            'participant.id_in_session',
            'tests.export.1.player.id_in_group',
            'tests.export.1.group.group_field',
            'tests.export.1.subsession.subsession_field',
            'tests.export.2.subsession.subsession_field',
        ]:
            self.assertIn('{}'.format(expected_text), header_row)

        # 3.14 should be in the CSV without any currency formatting
        for expected_text in ['should be in export CSV', ',3.14,']:
            self.assertIn(expected_text, csv_text)

        # True/False should be converted to 1/0
        self.assertNotIn('False', csv_text)

        # test alignment
        for row in rows[1:]:
            participant_code = re.search(',ALIGN_TO_PARTICIPANT_(\w+),', row).group(1)
            self.assertIn(r',{},'.format(participant_code), row)

            # both rounds should have it
            self.assertEqual(
                row.count(',ALIGN_TO_PARTICIPANT_{}'.format(participant_code)),
                Constants.num_rounds)

            session_code = re.search(',ALIGN_TO_SESSION_(\w+),', row).group(1)
            self.assertIn(',{},'.format(session_code), row)

            group_id = re.search(',GROUP_(\d+),', row).group(1)
            self.assertIn(',ALIGN_TO_GROUP_{},'.format(group_id), row)

            subsession_id = re.search(',SUBSESSION_(\d+),', row).group(1)
            self.assertIn(',ALIGN_TO_SUBSESSION_{},'.format(subsession_id), row)


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
            otree.export.export_docs(buff, app)
            self.assertEqual(response.content, buff.getvalue().encode('utf-8'))

    def test_simple_game_export_data(self):
        self.session_test("simple")

    def test_misc_1p_game_export_docs(self):
        self.session_test("misc_1p")

    def test_misc_3p_game_export_docs(self):
        self.session_test("misc_3p")


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
        otree.export.export_time_spent(buff)
        self.assertEqual(response.content, buff.getvalue().encode('utf-8'))
