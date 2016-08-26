#!/usr/bin/env python
# -*- coding: utf-8 -*-

import itertools

from mock import patch

import six
from django.core.management import call_command
from otree.models import Session

from .base import TestCase


class TestRounds(TestCase):

    def setUp(self):

        call_command('create_session', 'rounds', "4")
        self.session = Session.objects.get()
        self.subsession_3 = self.session.get_subsessions()[2]

    def test_in_rounds(self):
        subsession = self.subsession_3
        group = subsession.get_groups()[0]
        player = group.get_player_by_id(1)

        for obj in [subsession, group, player]:
            prev_objs = obj.in_all_rounds()
            self.assertEqual([o.round_number for o in prev_objs], [1,2,3])

            prev_objs = obj.in_previous_rounds()
            self.assertEqual([o.round_number for o in prev_objs], [1,2])

            prev_objs = obj.in_rounds(2, 3)
            self.assertEqual([o.round_number for o in prev_objs], [2, 3])

            prev = obj.in_round(1)
            self.assertEqual(prev.round_number, 1)

        prev_groups = group.in_all_rounds()
        group_participants = [p.participant for p in group.get_players()]
        for prev_group in prev_groups:
            self.assertEqual(
                group_participants,
                [p.participant for p in prev_group.get_players()]
            )

        prev_players = player.in_all_rounds()
        for prev_player in prev_players:
            self.assertEqual(
                player.participant,
                prev_player.participant)

