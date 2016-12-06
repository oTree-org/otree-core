#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.management import call_command
from django.core.urlresolvers import reverse
from otree.models import Session
from .base import TestCase
import splinter

class TestAdminReport(TestCase):

    def setUp(self):
        call_command('create_session', 'admin_report', "1")
        self.session = Session.objects.get()
        self.browser = splinter.Browser('django') # type: splinter.Browser


    def test_load(self):
        url = reverse('AdminReport', args=[self.session.code])
        browser = self.browser
        browser.visit(url)

        for substring in ['42', '43', 'round 1']:
            self.assertTrue(browser.is_text_present(substring))

        browser.fill('app_name', 'tests.admin_report')
        browser.fill('round_number', '2')
        button = browser.find_by_id('submit')
        # Interact with elements
        button.click()
        self.assertIn('round 2', browser.html)
