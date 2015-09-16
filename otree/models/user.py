#!/usr/bin/env python
# -*- coding: utf-8 -*-

from otree_save_the_change.mixins import SaveTheChange

from otree.db import models
from otree.models.session import Session


class User(SaveTheChange, models.Model):

    _index_in_game_pages = models.PositiveIntegerField(
        default=0,
        doc='Index in the list of pages  views_module.page_sequence'
    )

    session = models.ForeignKey(
        Session, related_name='%(app_label)s_%(class)s'
    )

    round_number = models.PositiveIntegerField()

    class Meta:
        abstract = True
