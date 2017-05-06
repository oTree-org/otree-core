from otree.session import create_session
from otree.models.participant import Participant
from otree.bots.bot import ParticipantBot
from .base import TestCase
from tests.timeout_submission.models import Player, Constants
from tests.timeout_submission import views
import django.test
from otree.api import Submission, Currency, Page

test_client = django.test.Client()

# tuple instead of dict so we don't mutate it by mistake
default_submission = (
    ('f_bool', True),
    ('f_char', 'hello'),
    ('f_currency', Currency(2)),
    ('f_float', 0.1),
    ('f_posint', 3),
)

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
