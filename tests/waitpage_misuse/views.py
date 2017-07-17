# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from otree.api import WaitPage
from tests.utils import BlankTemplatePage as Page
from .models import Constants


class GBATWaitPage(WaitPage):
    group_by_arrival_time = True

    def get_players_for_group(self, waiting_players):
        for attr in ['player', 'participant', 'group']:
            try:
                getattr(self, attr).id
            except AttributeError:
                pass
            else:
                raise AssertionError(
                    'You should not be able to reference '
                    'self.{player, participant, group} '
                    'in get_players_for_group'
                )
        if len(waiting_players) == 2:
            return waiting_players

class RegularWait(WaitPage):
    def after_all_players_arrive(self):
        for attr in ['player', 'participant']:
            try:
                obj = getattr(self, attr)
                obj.id = 100
            except AttributeError:
                pass
            else:
                raise AssertionError(
                    'You should not be able to reference self.participant '
                    'or self.player in after_all_players_arrive'
                )


class AllGroupsWait(WaitPage):
    wait_for_all_groups = True

    def after_all_players_arrive(self):
        for attr in ['player', 'participant', 'group']:
            try:
                obj = getattr(self, attr)
                obj.id = 100
            except AttributeError:
                pass
            else:
                raise AssertionError(
                    'You should not be able to reference '
                    'self.{player, participant, group} '
                    'in this method'
                )



class Page1(Page):
    pass


page_sequence = [
    GBATWaitPage,
    RegularWait,
    AllGroupsWait,
    Page1,
]
