from otree.api import Submission, SubmissionMustFail
from .base import TestCase
import otree.session
from otree.bots.runner import session_bot_runner_factory, test_bots
import logging
import unittest.mock
from tests.bots_cases.tests import PlayerBot
import tests.bots_cases.views


class TestBots(TestCase):
    def test_bot_runs(self):

        session = otree.session.create_session(
            session_config_name='bots_raise',
            num_participants=2,
            use_cli_bots=True,
            bot_case_number=0,
        )

        bot_runner = session_bot_runner_factory(session)

        with self.assertRaises(ZeroDivisionError):
            bot_runner.play()

    def test_bots_check_html(self):

        session = otree.session.create_session(
            session_config_name='bots_check_html',
            num_participants=1,
            use_cli_bots=True,
            bot_case_number=0,
        )

        with self.settings(BOTS_CHECK_HTML=True):
            bot_runner = session_bot_runner_factory(session)
            try:
                bot_runner.play()
            except AssertionError as exc:
                # AssertionError should say something about check_html
                raises_correct_message = 'check_html' in str(exc) and 'Page2' in str(exc)
            else:
                raises_correct_message = False
            if not raises_correct_message:
                raise AssertionError('bots check_html not working properly')



    def test_bot_bad_post(self):
        """
        Test that posting bad data without using SubmitInvalid
        will raise an error.
        """

        session = otree.session.create_session(
            session_config_name='bots_bad_post',
            num_participants=1,
            use_cli_bots=True,
            bot_case_number=0,
        )

        bot_runner = session_bot_runner_factory(session)

        with self.assertRaises(AssertionError):
            # need to disable log output, because this triggers an exception
            # that is logged to stdout
            logging.disable(logging.CRITICAL)
            bot_runner.play()
            logging.disable(logging.NOTSET)

    def test_bots_submission_varieties(self):
        '''Testing different syntaxes for a submission'''
        Page1 = tests.bots_cases.views.Page1
        for submission in [
            Submission(Page1),
            Submission(Page1, {}),
            SubmissionMustFail(Page1, check_html=False),
            Submission(Page1, {'f2': True}, check_html=False),
            SubmissionMustFail(Page1, {}),
            Submission(Page1, {'f3': True}),
        ]:
            self.assertIsInstance(submission, dict)

    @unittest.mock.patch.object(PlayerBot, 'case1')
    @unittest.mock.patch.object(PlayerBot, 'case2')
    def test_cases(self, patched_case2, patched_case1):
        '''
        Test that all cases are run
        '''

        test_bots('bots_cases', 1, False)
        self.assertTrue(patched_case1.called)
        self.assertTrue(patched_case2.called)
