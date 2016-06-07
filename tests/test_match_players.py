#!/usr/bin/env python
# -*- coding: utf-8 -*-

import itertools

from mock import patch

import six

from django.core.management import call_command

from otree.models import Session
from otree import matching

from .base import TestCase
from .multi_player_game import models as mpg_models


class TestMatchPlayers(TestCase):

    def setUp(self):
        patcher = patch.object(mpg_models.Subsession, "before_session_starts")
        patcher.start()
        self.addCleanup(patcher.stop)

        call_command('create_session', 'multi_player_game', "9")
        self.session = Session.objects.get()

    def assertCountEqual(self, *args, **kwargs):
        # In Python 2, this method is called ``assertItemsEqual``.
        if six.PY2:
            return self.assertItemsEqual(*args, **kwargs)
        return super(TestMatchPlayers, self).assertCountEqual(*args, **kwargs)

    def assert_groups_contains(self, groups, expected):
        actual = tuple(itertools.chain(*groups))
        self.assertCountEqual(actual, expected)

    def assert_groups_sizes(self, groups, expected):
        actual = [len(g) for g in groups]
        self.assertCountEqual(actual, expected)

    def assert_matchs(self, matching_function, validator):
        previous = []
        for subssn in self.session.get_subsessions():
            sizes = [
                len(g) for g in subssn.get_group_matrix()]
            new_group_matrix = matching_function(subssn)
            self.assert_groups_sizes(new_group_matrix, sizes)
            validator(
                new_group_matrix, subssn, subssn.get_players(),
                subssn.round_number, previous)
            previous.append(new_group_matrix)

    def assert_same_order_participants(self, actual, expected):
        actual = [p.participant for p in actual]
        expected = [p.participant for p in expected]
        self.assertListEqual(actual, expected)

