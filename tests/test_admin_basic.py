#!/usr/bin/env python
# -*- coding: utf-8 -*-

import django.test.client
from .base import TestCase
from django.conf import settings
from .utils import get_path
from django.core.urlresolvers import reverse
import sys
import importlib


def reload_urlconf():
    if settings.ROOT_URLCONF in sys.modules:
        module = sys.modules[settings.ROOT_URLCONF]
    else:
        module = importlib.import_module(settings.ROOT_URLCONF)
    importlib.reload(module)


class TestAdminBasic(TestCase):

    def setUp(self):
        self.browser = django.test.client.Client()

    def test_admin_basic(self):
        for tab in [
            'demo',
            'sessions',
            'rooms',
            'create_session',
            'server_check',
            'accounts/login'
        ]:
            response = self.browser.get('/{}/'.format(tab), follow=True)
            self.assertEqual(response.status_code, 200)

    def test_login(self):
        login_url = '/accounts/login/'
        resp = self.browser.post(
            login_url,
            data={
                'username': settings.ADMIN_USERNAME,
                'password': settings.ADMIN_PASSWORD,
            },
            follow=True
        )

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(login_url, get_path(resp, if_no_redirect=login_url))

    def test_auth_level(self):

        # whether you should be granted access when not logged in,
        # based on AUTH_LEVEL
        auth_level_outcomes = {
            'STUDY': {
                'OutOfRangeNotification': True,
                'DemoIndex': False,
                'ExportIndex': False,
            },
            'DEMO': {
                'OutOfRangeNotification': True,
                'DemoIndex': True,
                'ExportIndex': False,
            },
            '': {
                'OutOfRangeNotification': True,
                'DemoIndex': True,
                'ExportIndex': True,
            }
        }

        for AUTH_LEVEL in auth_level_outcomes:
            with self.settings(AUTH_LEVEL=AUTH_LEVEL):
                reload_urlconf()
                for url_name in auth_level_outcomes[AUTH_LEVEL]:
                    url = reverse(url_name)
                    resp = self.browser.get(url, follow=True)
                    is_login_page = any(
                        ['accounts/login' in ele[0]
                         for ele in resp.redirect_chain])
                    access_granted = not is_login_page
                    self.assertEqual(
                        access_granted,
                        auth_level_outcomes[AUTH_LEVEL][url_name],
                        msg='AUTH_LEVEL={}, url_name={}, access_granted={}'.format(
                            AUTH_LEVEL, url_name, access_granted
                        )
                    )
            # reload URLconf to restore back to its original state,
            # so other tests can run normally
            reload_urlconf()