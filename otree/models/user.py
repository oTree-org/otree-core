#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

from save_the_change.mixins import SaveTheChange

from otree.db import models
from otree.models.session import Session, SessionExperimenter


class User(SaveTheChange, models.Model):

    _index_in_game_pages = models.PositiveIntegerField(
        default=0,
        doc='Index in the list of pages returned by views_module.pages()'
    )

    session = models.ForeignKey(
        Session, related_name='%(app_label)s_%(class)s'
    )

    round_number = models.PositiveIntegerField()

    class Meta:
        abstract = True


class Experimenter(User):

    session_experimenter = models.ForeignKey(
        SessionExperimenter, null=True, related_name='experimenter'
    )

    subsession_content_type = models.ForeignKey(
        ContentType, null=True, related_name='experimenter'
    )
    subsession_object_id = models.PositiveIntegerField(null=True)
    subsession = generic.GenericForeignKey(
        'subsession_content_type', 'subsession_object_id',
    )

    class Meta:
        app_label = 'otree'

    @property
    def _session_user(self):
        return self.session_experimenter

    def _pages_as_urls(self):
        return self.subsession._experimenter_pages_as_urls()
