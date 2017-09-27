import idmap.tls
import django.db
from django.core.management import call_command
from otree.models import Participant, Session
from otree.views.abstract import Page
from otree.db.idmap import (
    save_objects, use_cache)
import django.test
from .utils import TestCase
import tests.simple.models as simple_models
from otree.session import create_session

class ModelTests(TestCase):
    def setUp(self):
        session = create_session('simple', num_participants=1)
        self.session_id = session.id
        self.player_id = simple_models.Player.objects.get(
                session_id=self.session_id).id

    def test_strong_refs(self):

        def inside_function():
            '''do these queries in a function so we can know use_strong_refs
            is working correctly
            '''
            player = simple_models.Player.objects.get(
                session_id=self.session_id, id_in_group=1
            )
            player.nonexistent_attribute = 'temp_value'
            group = player.group
            subsession = simple_models.Subsession.objects.get(
                session_id=self.session_id)
            session = player.session
            # do a query rather than FK lookup player.participant
            # to avoid participant from being cached on player
            # we want to make sure it actually goes into the IDmap cache
            participant = session.participant_set.first()

        with use_cache():
            inside_function()
            with self.assertNumQueries(0):
                # if you use get() by PK, it skips the query entirely
                player = simple_models.Player.objects.get(id=self.player_id)
                self.assertEqual(player.nonexistent_attribute, 'temp_value')
                group = player.group
                subsession = player.subsession
                session = player.session
                # this shouldn't do a query because we know the participant PK
                # (it's player.participant_id), and the participant
                # should have been stored in the IDmap cache
                participant = player.participant
            with self.assertNumQueries(1):
                # this does a query because we don't know the pk.
                # but after retrieving the object, it checks the cache
                # if that item already exists.
                player = simple_models.Player.objects.get(
                    session_id=self.session_id, id_in_group=1
                )


class ViewTests(TestCase):

    def setUp(self):

        call_command('create_session', 'simple', '1')
        participant = Participant.objects.get()
        self.client.get(participant._start_url(), follow=True)
        self.participant_pk = participant.pk

    def test_not_lazy(self):

        with use_cache():

            page = Page()
            participant = Participant.objects.get(pk=self.participant_pk)
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
            participant = Participant.objects.get(pk=self.participant_pk)
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
