#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.management import call_command

from otree.models import Session
import django.test.client
from .base import TestCase


class TestAdminBasic(TestCase):

    def setUp(self):
        self.browser = django.test.client.Client()

    def _test_tabs(self):
        for tab in [
            'demo',
            'admin',
            'persistent_lab_urls',
            'create_session',
            'create_session/multi_player_game'
        ]:
            response = self.browser.get('/{}/'.format(tab), follow=True)
            self.assertEqual(response.status_code, 200)




