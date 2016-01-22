#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.management import call_command

from otree.models import Session
import django.test.client
from .base import TestCase


class TestSessionAdmin(TestCase):

    def setUp(self):
        call_command('create_session', 'multi_player_game', "9")
        self.session = Session.objects.get()
        self.browser = django.test.client.Client()

    def test_tabs(self):
        tabs = [
            'SessionDescription',
            'SessionMonitor',
            'SessionPayments',
            'SessionResults',
            'SessionStartLinks',
            'AdvanceSession',
            'SessionFullscreen',
        ]
        urls = ['/{}/1'.format(PageName) for PageName in tabs]

        urls.extend([
            '/sessions/{}/participants/'.format(self.session.code),
        ])

        for url in urls:
            response = self.browser.get(url, follow=True)
            if response.status_code != 200:
                raise Exception('{} returned 400'.format(url))
