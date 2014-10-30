import sys
from StringIO import StringIO

from django.test import TestCase
from django.core.management import call_command

from otree.models import Session
from tests.simple_game.models import Subsession, Player


class TestCreateSessionsCommand(TestCase):
    def setUp(self):
        self._original_stdout = sys.stdout
        self.stdout = sys.stdout = StringIO()

    def tearDown(self):
        sys.stdout = self._original_stdout

    def get_output(self):
        self.stdout.seek(0)
        return self.stdout.read()

    def test_create_sessions_output(self):
        call_command('create_sessions', 'simple_game', 1)
        output = self.get_output()

        self.assertTrue('tests.simple_game' in output)

    def test_create_two_sessions_output(self):
        call_command('create_sessions', 'simple_game', 2)
        output = self.get_output()

        lines = output.strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], 'Creating sessions...')
        self.assertTrue('tests.simple_game' in lines[1])
        self.assertTrue('tests.simple_game' in lines[2])

    def test_create_one_session(self):
        call_command('create_sessions', 'simple_game', 1)

        self.assertEqual(Session.objects.count(), 1)
        session = Session.objects.get()
        self.assertEqual(session.type_name, 'simple_game')

        self.assertEqual(Subsession.objects.count(), 1)
        subsession = Subsession.objects.get()
        self.assertEqual(session.first_subsession, subsession)

        self.assertEqual(Player.objects.count(), 1)
        player = Player.objects.get()
        self.assertEqual(player.session, session)
        self.assertEqual(player.subsession, subsession)
