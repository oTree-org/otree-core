#!/usr/bin/env python
# -*- coding: utf-8 -*-

import itertools

from mock import patch

import six

from django.core.management import call_command

from otree.models import Session
from otree import match_players

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

    def assert_matchs(self, names, validator):
        previous = []
        for alias in names:
            func = match_players.MATCHS[alias]
            for subssn in self.session.get_subsessions():
                sizes = [
                    len(g) for g in match_players.players_x_groups(subssn)]
                groups = func(subssn)
                self.assert_groups_sizes(groups, sizes)
                validator(
                    groups, subssn, subssn.get_players(),
                    subssn.round_number, previous)
                previous.append(groups)

    def assert_aliases(self, fnc, expected):
        actual = [k for k, v in match_players.MATCHS.items() if v is fnc]
        self.assertCountEqual(actual, expected)

    def assert_same_order_participants(self, actual, expected):
        actual = [p.participant for p in actual]
        expected = [p.participant for p in expected]
        self.assertListEqual(actual, expected)

    def test_random(self):
        names = ["random", "uniform", "players_random"]

        def validator(groups, subssn, players, round_number, previous):
            self.assert_groups_contains(groups, players)

        self.assert_aliases(match_players.players_random, names)
        self.assert_matchs(names, validator)

    def test_round_robin(self):
        names = ["perfect_strangers", "round_robin"]

        def validator(groups, subssn, players, round_number, previous):
            self.assert_groups_contains(groups, players)

        self.assert_aliases(match_players.round_robin, names)
        self.assert_matchs(names, validator)

    def test_partners(self):
        names = ["partners"]

        def validator(groups, subssn, players, round_number, previous):
            self.assert_groups_contains(groups, players)
            if previous:
                for ag, pg in six.moves.zip(groups, previous[-1]):
                    self.assert_same_order_participants(ag, pg)

        self.assert_aliases(match_players.partners, names)
        self.assert_matchs(names, validator)

    def test_reversed(self):
        names = ["reversed", "players_reversed"]

        def validator(groups, subssn, players, round_number, previous):
            self.assert_groups_contains(groups, players)
            if previous:
                for ag, pg in six.moves.zip(groups, previous[-1]):
                    self.assert_same_order_participants(ag, reversed(pg))

        self.assert_aliases(match_players.players_reversed, names)
        self.assert_matchs(names, validator)
