import idmap.tls
import django.db
from django.core.management import call_command
from otree.models import Participant, Session
from otree.views.abstract import Page
from otree.db.idmap import (
    save_objects, use_cache)
import django.test
from .utils import TestCase, run_bots

class ViewTests(TestCase):


    def setUp(self):

        call_command('create_session', 'simple', '1')
        participant = Participant.objects.get()
        client = django.test.Client()
        client.get(participant._start_url())

    def test_not_lazy(self):

        with use_cache():

            page = Page()
            participant = Participant.objects.get()
            # 2 queries: for all objects, and for player_lookup
            with self.assertNumQueries(2):
                page.set_attributes(participant)
            with self.assertNumQueries(0):
                _ = page.player.id
                _ = page.group.id
                _ = page.session.id
                _ = page.subsession.id
                _ = page.participant.id

    def test_lazy(self):
        with use_cache():
            page = Page()
            participant = Participant.objects.get()
            # set_attributes causes player_lookups

            # only makes 1 query, for player_lookup
            with self.assertNumQueries(1):
                page.set_attributes(participant, lazy=True)
            # query only when we need it
            with self.assertNumQueries(1):
                _ = page.player.id
            # cached in idmap
            with self.assertNumQueries(0):
                _ = page.player.id
