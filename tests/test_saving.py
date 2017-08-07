from unittest.mock import Mock
from unittest import mock
import idmap.tls
import django.db
from django.core.management import call_command
from otree.common import Currency
from otree.db import models
from otree.models import Participant, Session
from otree.db.idmap import save_objects, _get_save_objects_model_instances
from .base import TestCase





import django.db.models


class SavingTests(TestCase):
    # We need to make sure to flush the idmap cache here after every save in
    # order to prevent getting values that do not actually represent the DB
    # values.

    def test_dont_save_if_no_change(self):
        with self.assertNumQueries(0):
            save_objects()

        call_command('create_session', 'simple', '1')
        # Reset cache.
        idmap.tls.init_idmap()

        participant = Participant.objects.get()

        # We keep track of the participant.
        instances = _get_save_objects_model_instances()
        self.assertEqual(instances, [participant])

        # But we won't save the participant since we didn't change it.
        with self.assertNumQueries(0):
            save_objects()


    def test_save_only_changed_fields(self):
        call_command('create_session', 'simple', '1')
        # Reset cache.
        idmap.tls.init_idmap()

        participant = Participant.objects.get()
        with mock.patch.object(django.db.models.Model, 'save') as patched_save:
            save_objects()
            # no change, so should be no call
            patched_save.assert_not_called()

            participant.code = 'hello'
            save_objects()
            # but is this necessarily the only argument? no
            patched_save.assert_called_once_with(update_fields=['code'])


    def test_nested_changes(self):
        call_command('create_session', 'simple', '1')
        # Reset cache.
        idmap.tls.init_idmap()

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

        # Reset cache.
        idmap.tls.init_idmap()

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


class PickleFieldModel(models.Model):
    vars = models._PickleField(default=dict)
    integer = models.IntegerField(default=0)


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

    def test_vars_are_saved(self):
        instance = PickleFieldModel(integer=1)
        instance.vars = {'a': 'b'}
        instance.save()

        PickleFieldModel.flush_cached_instance(instance)

        instance = PickleFieldModel.objects.get()
        self.assertEqual(instance.integer, 1)
        self.assertEqual(instance.vars, {'a': 'b'})

        instance.vars = {'c': 'd'}
        instance.save()

        PickleFieldModel.flush_cached_instance(instance)

        instance = PickleFieldModel.objects.get()
        self.assertEqual(instance.vars, {'c': 'd'})

    def test_other_vars_are_saved(self):
        instance = PickleFieldModel()
        instance.vars = {'a': 'b'}
        instance.save()

        PickleFieldModel.flush_cached_instance(instance)

        instance = PickleFieldModel.objects.get()
        self.assertEqual(instance.vars, {'a': 'b'})

        instance.integer = 2
        instance.vars['a'] = 'd'
        instance.save()

        PickleFieldModel.flush_cached_instance(instance)

        instance = PickleFieldModel.objects.get()
        self.assertEqual(instance.integer, 2)
        self.assertEqual(instance.vars, {'a': 'd'})
