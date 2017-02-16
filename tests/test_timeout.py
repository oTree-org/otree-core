from django.core.management import call_command
from otree.models.participant import Participant
from otree.bots.bot import ParticipantBot
from .base import TestCase
from tests.timeout_submission.models import Player, Constants
from tests.timeout_submission import views
from otree import constants_internal
import django.test
from otree.api import Submission, Currency


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
        call_command('create_session', 'timeout_submission', "1")

    def test_valid(self):
        '''valid form'''
        values = dict(default_submission)

        self.submit_form(values)
        self.assert_player_fields(dict(default_submission))

    def test_invalid_fields(self):
        '''invalid individual fields but passes error_message'''
        values = dict(default_submission)
        values.pop('f_float')
        values['f_posint'] = -1

        self.submit_form(values)

        values = dict(default_submission)
        values['f_float'] = 0
        values['f_posint'] = 0

        self.assert_player_fields(values)

    def test_valid_but_invalid_error_message(self):
        '''valid individual fields but passes error_message'''
        values = dict(default_submission)
        values['f_char'] = Constants.invalid_f_char

        self.submit_form(values)

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

        self.submit_form(values)

        auto_submit_defaults = {
            'f_bool': False,
            'f_char': '',
            'f_currency': Currency(0),
            'f_float': 0,
            'f_posint': 0,
        }

        self.assert_player_fields(auto_submit_defaults)

    def submit_form(self, values):
        values = values.copy()
        participant = Participant.objects.get()
        bot = ParticipantBot(participant, load_player_bots=False)
        bot.open_start_url()
        values[constants_internal.auto_submit] = True
        bot.submit(Submission(views.Page1, values))

    def assert_player_fields(self, values):
        player = Player.objects.get()
        for field_name, value in values.items():
            self.assertEqual(getattr(player, field_name), value, msg=field_name)
