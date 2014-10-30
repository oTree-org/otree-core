from django.test import TestCase
from django.core.management import call_command

from otree.models import Session
from tests.simple_game.models import Subsession, Player
from tests.utils import capture_stdout


class TestCreateSessionsCommand(TestCase):
    def test_create_sessions_output(self):
        with capture_stdout() as output_stream:
            call_command('create_sessions', 'simple_game', 1)
        output = output_stream.read()

        self.assertTrue('tests.simple_game' in output)

    def test_create_two_sessions_output(self):
        with capture_stdout() as output_stream:
            call_command('create_sessions', 'simple_game', 2)
        output = output_stream.read()

        lines = output.strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], 'Creating sessions...')
        self.assertTrue('tests.simple_game' in lines[1])
        self.assertTrue('tests.simple_game' in lines[2])

    def test_create_one_session(self):
        with capture_stdout():
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
