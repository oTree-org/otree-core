from unittest.mock import Mock
from unittest import mock
import idmap.tls
import django.db
from django.core.management import call_command
from otree.common import Currency
from otree.db import models
from otree.models import Participant, Session
from otree.models.varsmixin import ModelWithVars
from otree.db.idmap import (
    save_objects, _get_save_objects_model_instances, use_cache)
from tests import TestCase
from tests.simple.models import Player
from otree.db.serializedfields import VarsError
from otree.api import BaseConstants
import django.db.models
from .utils import run_bots
import numpy

class SavingTests(TestCase):
    # We need to make sure to flush the idmap cache here after every save in
    # order to prevent getting values that do not actually represent the DB
    # values.

    def test_dont_save_if_no_change(self):
        call_command('create_session', 'simple', '1')

        with use_cache():
            participant = Participant.objects.get()

            # We keep track of the participant.
            instances = _get_save_objects_model_instances()
            self.assertEqual(instances, [participant])

            # But we won't save the participant since we didn't change it.
            with self.assertNumQueries(0):
                save_objects()


    def test_save_only_changed_fields(self):
        call_command('create_session', 'simple', '1')
        with use_cache():
            participant = Participant.objects.get()
            with mock.patch.object(django.db.models.Model, 'save') as patched_save:
                save_objects()
                # in save-the-change 2017 version, save is not called at all
                patched_save.assert_called_once_with(update_fields=[])

                participant.code = 'hello'
                save_objects()
                # but is this necessarily the only argument? no
                patched_save.assert_called_with(update_fields=['code'])


    def test_nested_changes(self):
        call_command('create_session', 'simple', '1')
        # Reset cache.
        with use_cache():
            # Query participant via session.
            session = Session.objects.get()
            participant = session.participant_set.get()
            participant.is_on_wait_page = not participant.is_on_wait_page

            # Save participant.
            with self.assertNumQueries(1):
                save_objects()

    def test_with_app_models(self):
        call_command('create_session', 'simple', '2')

        from .simple.models import Player

        with use_cache():
            players = Player.objects.all()
            self.assertEqual(len(players), 2)

            group = players[0].group
            group.save = Mock()
            group.round_number += 1

            # Query session object to test that it's loaded..
            group.session
            participants = group.session.participant_set.all()

            all_instances = {
                players[0],
                players[1],
                group,
                group.session,
                participants[0],
                participants[1]
            }

            self.assertEqual(
                set(_get_save_objects_model_instances()),
                all_instances)

            # No queries are executed. The group model shall be saved, but we
            # mocked out the save method. All other models should be left
            # untouched.
            with self.assertNumQueries(0):
                save_objects()

            self.assertTrue(group.save.called)

class SavingBots(TestCase):
    def test_bots(self):
        run_bots('saving', 1)


class PickleFieldTests(TestCase):

    def test_pickle(self):
        self.test_values = [
            1, 1.33,
            None,
            [1, 2, 3., {}, ["coso", None, {}]],
            {"foo": [], "algo": None, "spam": [1, 2, 3.]},
            [],
            {},
            {1.5: 2},
            {Currency(1): Currency(2)},
            {1,2,3}
        ]
        for value in self.test_values:
            field = models._PickleField(default=value)
            serialized = field.get_prep_value(value)
            restored = field.to_python(serialized)
            self.assertEquals(value, restored)


class TestModelWithVars(ModelWithVars):
    pass


class Constants(BaseConstants):
    alist = [1,2]


class VarsTests(TestCase):

    def test_vars_are_saved(self):
        o = TestModelWithVars.objects.create()
        o.vars['a'] = 'b'
        o.save()

        o = TestModelWithVars.objects.get()
        self.assertEqual(o.vars, {'a': 'b'})

        o.vars['a'] = 'd'
        o.save()

        o = TestModelWithVars.objects.get()
        self.assertEqual(o.vars, {'a': 'd'})

    def test_forbid_storing_models(self):
        call_command('create_session', 'simple', '1')

        session = Session.objects.get()
        participant = Participant.objects.get()
        player = Player.objects.get()

        for value in [
            player,
            [player],
            {1: player},
            participant
        ]:
            session.vars['something_with_a_model'] = value
            with self.assertRaises(VarsError):
                session.save()

    def test_storing_constants(self):

        self.assertEqual(Constants.alist, [1,2])
        o = TestModelWithVars.objects.create()
        # users should always be using .copy(), even when assigning to vars,
        # because they might modify it before it's saved.
        o.vars['alist'] = Constants.alist.copy()
        o.save()

        o = TestModelWithVars.objects.get()
        vars_alist = o.vars['alist']
        self.assertEqual(vars_alist, Constants.alist)
        vars_alist.append(3)

        self.assertEqual(vars_alist, [1,2,3])
        # should not modify the original
        self.assertEqual(Constants.alist, [1,2])

    def test_numpy(self):
        '''
        https://github.com/karanlyons/django-save-the-change/issues/27

        The bug occurs when the dict keys are the same,
        so it recurses to check equality of the values,
        and one of the values is a numpy array

        '''
        o = TestModelWithVars.objects.create()
        o.vars['array'] = numpy.array([0,0])
        o.save()

        o = TestModelWithVars.objects.get()
        array = o.vars['array']

        # test that it was round-tripped without data loss
        self.assertIsInstance(array, numpy.ndarray)
        # can't use equality on numpy arrays
        self.assertEqual(list(array), [0,0])

        o.vars['array'][0] = 1
        o.save()
