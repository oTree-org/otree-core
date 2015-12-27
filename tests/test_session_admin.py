
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import itertools

from mock import patch

import six

from django.core.management import call_command

from otree.models import Session
from otree import match_players
import django.test.client
from .base import TestCase
from .multi_player_game import models as mpg_models


class TestMatchPlayers(TestCase):

    def setUp(self):
        call_command('create_session', 'multi_player_game', "9")
        self.session = Session.objects.get()
        self.browser = django.test.client.Client()

    def test_tabs(self):
        for tab in [
            'SessionDescription',
            'SessionMonitor',
            'SessionPayments',
            'SessionResults',
            'SessionStartLinks',
        ]:
            response = self.browser.get('/{}/1/'.format(tab), follow=True)
            self.assertEqual(response.status_code, 200)



