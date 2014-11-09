from django.test import TestCase
from django.core.management import call_command

from otree.models import Session
from tests.simple_game.models import Subsession, Player
from tests.utils import capture_stdout


class TestCreateSessionsCommand(TestCase):
    def test_create_two_sessions_output(self):
        num_sessions = 2
        with capture_stdout() as output_stream:
            for i in range(num_sessions):
                call_command('create_session', 'simple_game', 1)
        output = output_stream.read()

        lines = output.strip().splitlines()
        self.assertEqual(len(lines), num_sessions)
        self.assertEqual(lines[0], 'Creating session...')

    def test_create_one_session(self):
        with capture_stdout():
            call_command('create_session', 'simple_game', 1)

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
