from .base import TestCase
from django.core.management import call_command
from otree.models import Session
import django.test
import time
from tests.group_by_arrival_time_heartbeat.models import Subsession

class TestGBAT(TestCase):

    def setUp(self):
        call_command('create_session', 'group_by_arrival_time_heartbeat', '4')
        self.session = Session.objects.get()
        self.participants = list(self.session.get_participants())
        self.client = django.test.Client()

    def get(self, url):
        self.client.get(url, follow=True)

    def test_heartbeat(self):

        p1, p2, p3, p4 = self.participants
        self.get(p1._start_url())
        # backdate p1's visit, to simulate them being idle for a while
        p1._last_request_timestamp = time.time() - 30
        p1.save()
        self.get(p2._start_url())
        self.get(p3._start_url())

        subsession = Subsession.objects.get()
        player1, player2, player3, player4 = subsession.get_players()
        self.assertEqual(player2.group, player3.group)
        self.assertNotEqual(player1.group, player2.group)

