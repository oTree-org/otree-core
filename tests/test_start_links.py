from django.core.urlresolvers import reverse
import splinter
import unittest
from otree.session import create_session
from .utils import get_path
from tests import TestCase
from django.core.management import call_command
from otree.models.session import Session
from otree.models.participant import Participant


class TestSessionWideLink(TestCase):

    def setUp(self):
        self.browser = splinter.Browser('django') # type: splinter.Browser


    def test_open_participant_links(self):
        br = self.browser

        def go(url):
            br.visit(url)
            self.assertEqual(br.status_code, 200)

        call_command('create_session', 'simple', '3')
        session = Session.objects.get()

        without_label = reverse(
            'JoinSessionAnonymously', args=[session._anonymous_code])

        go(without_label)
        go(without_label)
        visited_count = Participant.objects.filter(visited=True).count()
        self.assertEqual(visited_count, 2)

        label = 'John'
        with_label = without_label + '?participant_label={}'.format(label)
        with_label2 = without_label + '?participant_label=John2'

        go(with_label)
        go(with_label)

        label_visited_count = Participant.objects.filter(
            visited=True, label=label).count()

        self.assertEqual(label_visited_count, 1)

        visited_count = Participant.objects.filter(
            visited=True).count()

        self.assertEqual(visited_count, 3)

        self.browser.visit(without_label)
        self.assertEqual(br.status_code, 404)

        self.browser.visit(with_label2)
        self.assertEqual(br.status_code, 404)
