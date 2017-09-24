from django.core.management import call_command
from django.core.urlresolvers import reverse
from otree.models import Session
import django.test.client
from .utils import TestCase


class TestSessionAdmin(TestCase):

    def setUp(self):
        call_command('create_session', 'misc_3p', "9")
        self.session = Session.objects.get()
        self.browser = django.test.client.Client()

    def test_tabs(self):
        p1 = self.session.participant_set.first()
        # have to load 1 participant so that the monitor view shows data
        self.client.get(p1._start_url(), follow=True)

        tabs = [
            'SessionDescription',
            'SessionMonitor',
            'SessionPayments',
            'SessionData',
            'SessionStartLinks',
            'SessionSplitScreen',
        ]
        urls = [reverse(PageName, args=[self.session.code]) for PageName in tabs]

        # REST feed
        urls.append('/sessions/{}/participants/'.format(self.session.code))

        for url in urls:
            response = self.browser.get(url, follow=True)
            if response.status_code != 200:
                raise Exception('{} returned 400'.format(url))

    def test_edit_session_properties(self):
        path = '/SessionEditProperties/{}/'.format(self.session.code)

        data = {
            'label': 'label_foo',
            'experimenter_name': 'experimenter_name_foo',
            'comment': 'comment_foo',
            'participation_fee': '3.14',
            'real_world_currency_per_point': '0.0314',
        }
        resp = self.browser.post(
            path=path,
            data=data,
            follow=True
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.browser.get(path, follow=True)
        self.assertEqual(resp.status_code, 200)

        html = resp.content.decode('utf-8')
        for val in data.values():
            self.assertIn(val, html)
