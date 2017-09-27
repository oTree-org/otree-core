from .utils import TestCase
from django.core.urlresolvers import reverse
from unittest.mock import patch
from tests.bots_cases.tests import PlayerBot
import otree.bots.browser as browser_bots

class CreateSessionTests(TestCase):

    @patch.object(PlayerBot, '__init__', return_value=None)
    def test_cases(self, patched_init):
        browser_bots.browser_bot_worker = browser_bots.Worker()
        self.client.post(
            reverse('CreateBrowserBotsSession'),
            data={
                'session_config_name': 'bots_cases',
                'num_participants': '1',
                'case_number': '1'
            }
        )
        calls = patched_init.call_args_list
        self.assertEqual(len(calls), 1)
        for call in calls:
            kwargs = call[1]
            self.assertEqual(kwargs['case_number'], 1)
