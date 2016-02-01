#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.management import call_command
from django.core.urlresolvers import reverse
from django.conf import settings
import django.test.client

from otree.models import Session
from otree.models.session import GlobalSingleton
from .base import TestCase


class TestDefaultSession(TestCase):

    def setUp(self):
        call_command('create_session', 'multi_player_game', "9")
        self.session = Session.objects.get()
        self.browser = django.test.client.Client()

    def test_default_session(self):
        url = reverse(
            'set_default_session',
            args=(self.session.pk,)
        )
        self.browser.get(url)
        global_singleton = GlobalSingleton.objects.get()
        self.assertTrue(
            global_singleton.default_session == self.session
        )
        url = reverse(
            'assign_visitor_to_default_session'
        )
        self.browser.get(
            url,
            data={
                'access_code_for_default_session':
                settings.ACCESS_CODE_FOR_DEFAULT_SESSION,
                'participant_label': 'PC-1'
            }
        )

        participant = self.session.participant_set.order_by('start_order')[0]
        self.assertTrue(participant.label == 'PC-1')
        url = reverse('unset_default_session')
        self.browser.get(url)
        global_singleton = GlobalSingleton.objects.get()
        self.assertTrue(global_singleton.default_session is None)
