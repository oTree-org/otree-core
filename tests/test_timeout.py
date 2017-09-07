from otree.session import create_session
from otree.models.participant import Participant
from otree.bots.bot import ParticipantBot
from .utils import TestCase
from tests.timeout_submission.models import Player, Constants
from tests.timeout_submission import views
import django.test
from otree.api import Submission, Currency, Page
import itertools
import time
import otree.timeout.tasks #.submit_expired_url.schedule(
from unittest.mock import patch, MagicMock

test_client = django.test.Client()

# tuple instead of dict so we don't mutate it by mistake
default_submission = (
    ('f_bool', True),
    ('f_char', 'hello'),
    ('f_currency', Currency(2)),
    ('f_float', 0.1),
    ('f_posint', 3),
)


class PageWithTimeout(Page):

    timeout_seconds = 50


class PageWithNoTimeout(Page):
    pass


class TestTimeout(TestCase):

    def get_page(self, PageClass, participant):
        page = PageClass()
        page.set_attributes(participant)
        page.request = MagicMock()
        page.request.path = 'foo'
        return page

    def setUp(self):
        session = create_session(
            session_config_name='timeout_submission',
            num_participants=1,
            use_cli_bots=True,
        )
        self.participant = session.get_participants()[0]

        # simulate opening the start link in the most minimal way
        # a more heavyweight approach would be to create the ParticipantBot
        # and open the start URL
        self.participant._index_in_pages = 1
        self.participant.save()

    @patch('time.time')
    def test_page_refresh(self, patched_time):
        '''
        Test that when you refresh a page, oTree still remembers the original
        timeout, rather creating a new one.
        '''

        patched_time.return_value = 100
        page = self.get_page(PageWithTimeout, self.participant)
        remaining_seconds = page.remaining_timeout_seconds()

        patched_time.return_value += 5
        page = self.get_page(PageWithTimeout, self.participant)
        remaining_seconds2 = page.remaining_timeout_seconds()

        # if you call it a second time, it should be the same
        self.assertEqual(remaining_seconds, remaining_seconds2 + 5)

    def test_timeout_scheduling(self):
        '''Loading a page with timeout should schedule a page submission'''

        with patch.object(otree.timeout.tasks.submit_expired_url, 'schedule') as schedule_method:
            page = self.get_page(PageWithNoTimeout, self.participant)
            page.remaining_timeout_seconds()

            self.assertFalse(schedule_method.called)

            page = self.get_page(PageWithTimeout, self.participant)
            page.remaining_timeout_seconds()

            self.assertTrue(schedule_method.called)

        # calling remaining_timeout_seconds() twice in the same request should
        # not schedule a second time. Testing this because the template calls
        # {{ view.remaining_timeout_seconds }} several times
        with patch.object(otree.timeout.tasks.submit_expired_url, 'schedule') as schedule_method:
            page.remaining_timeout_seconds()
            self.assertFalse(schedule_method.called)


class TestTimeoutSubmission(TestCase):

    def setUp(self):
        create_session(
            session_config_name='timeout_submission',
            num_participants=1,
            use_cli_bots=True,
        )

    def submit_form(self, values, timeout_happened):
        participant = Participant.objects.get()
        bot = ParticipantBot(participant, load_player_bots=False)
        bot.open_start_url()
        bot.submit(Submission(views.Page1, values, timeout_happened=timeout_happened))

    def timeout_submit_form(self, values):
        self.submit_form(values, timeout_happened=True)

    def assert_player_fields(self, values):
        player = Player.objects.get()
        for field_name, value in values.items():
            self.assertEqual(getattr(player, field_name), value, msg=field_name)

    def test_no_timeout(self):
        '''baseline test'''
        values = dict(default_submission)
        self.submit_form(values, timeout_happened=False)

        player = Player.objects.get()
        self.assertEqual(player.timeout_happened, False)

    def test_timeout_on_regular_page(self):
        participant = Participant.objects.get()
        bot = ParticipantBot(participant, load_player_bots=False)
        bot.open_start_url()
        bot.submit(Submission(views.Page1, {}, timeout_happened=True))
        # it should be OK to use timeout_happened=True, even if the page
        # has no timeout_seconds, because you can be simulating "advance slowest"
        bot.submit(Submission(views.PageWithoutTimeout, {}, timeout_happened=True))

    def test_valid(self):
        '''valid form'''
        values = dict(default_submission)

        self.timeout_submit_form(values)
        self.assert_player_fields(dict(default_submission))

        # test that timeout_happened was set
        player = Player.objects.get()
        self.assertEqual(player.timeout_happened, True)

    def test_invalid_fields(self):
        '''invalid individual fields but passes error_message'''
        values = dict(default_submission)
        values.pop('f_float')
        values['f_posint'] = -1

        self.timeout_submit_form(values)

        values = dict(default_submission)
        values['f_float'] = 0
        values['f_posint'] = 0

        self.assert_player_fields(values)

    def test_valid_but_invalid_error_message(self):
        '''valid individual fields but passes error_message'''
        values = dict(default_submission)
        values['f_char'] = Constants.invalid_f_char

        self.timeout_submit_form(values)

        auto_submit_defaults = {
            'f_bool': False,
            'f_char': '',
            'f_currency': Currency(0),
            'f_float': 0,
            'f_posint': 0,
        }

        self.assert_player_fields(auto_submit_defaults)

    def test_invalid_and_invalid_error_message(self):
        '''invalid individual fields and invalid error_message'''
        values = dict(default_submission)
        values['f_char'] = Constants.invalid_f_char
        values['f_posint'] = -1

        self.timeout_submit_form(values)

        auto_submit_defaults = {
            'f_bool': False,
            'f_char': '',
            'f_currency': Currency(0),
            'f_float': 0,
            'f_posint': 0,
        }

        self.assert_player_fields(auto_submit_defaults)
