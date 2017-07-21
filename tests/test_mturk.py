from collections import namedtuple
from django.core.management import call_command
from django.core.urlresolvers import reverse
from otree.common import RealWorldCurrency
from otree.models import Session, Participant
from otree.views.mturk import MTurkClient
import django.test.client
from unittest import mock
from unittest.mock import MagicMock
from .base import TestCase
from django.test import override_settings
from channels.test import ChannelLiveServerTestCase
from tests.base import OTreePhantomBrowser

from otree.views.mturk import get_mturk_client, function_to_mock
'''
from botocore.stub import Stubber
import botocore.session

def MockMTurk():
    return botocore.session.get_session().create_client('mturk')
'''

class TestMTurk(TestCase):

    def setUp(self):
        call_command('create_session', 'mturk', "2")
        self.session = Session.objects.get()
        self.browser = django.test.client.Client()

    def test_get_create_hit(self):
        url = reverse('MTurkCreateHIT', args=(self.session.code,))
        response = self.browser.get(url, follow=True)
        self.assertEqual(response.status_code, 200)

    @mock.patch('otree.views.mturk.get_mturk_client')
    def test_post_create_hit(self, mock_get_mturk_client):
        mocked_client = mock_get_mturk_client()

        mocked_client.create_hit.return_value = {'HIT': {'HITId': 'AAA', 'HITGroupId': 'BBB'}}
        url = reverse('MTurkCreateHIT', args=(self.session.code,))

        participation_fee = 1.47
        assignments = 6
        minutes_allotted_per_assignment = 60
        expiration_hours = 168

        response = self.browser.post(
            url,
            data=dict(
                in_sandbox = True,
                title = 'Title for your experiment',
                description = 'Description for your experiment',
                keywords = 'easy, bonus, choice, study',
                # different from the session config's default
                money_reward = participation_fee,
                assignments = assignments,
                minutes_allotted_per_assignment = minutes_allotted_per_assignment,
                expiration_hours = expiration_hours,
            ),
            follow=True
        )

        self.assertEqual(response.status_code, 200)

        mocked_client.create_hit.assert_called()
        # just a subset, things that are easy to mock
        expected_call_dict_subset = {
            'Title': 'Title for your experiment',
            'Description': 'Description for your experiment',
            'Keywords': 'easy, bonus, choice, study',
            'MaxAssignments': assignments,
            'Reward': str(participation_fee),
            'AssignmentDurationInSeconds': minutes_allotted_per_assignment*60,
            'LifetimeInSeconds': 60*60*expiration_hours
        }
        actual_call_dict = mocked_client.create_hit.call_args[1]
        self.assertLessEqual(expected_call_dict_subset.items(), actual_call_dict.items())

        mocked_client.create_hit.assert_called()

        session = Session.objects.get()
        self.assertEqual(session.config['participation_fee'], 1.47)


    @mock.patch('otree.views.mturk.get_mturk_client')
    def test_mturk_start(self, mock_get_mturk_client):
        mocked_client = mock_get_mturk_client()

        url = reverse('MTurkStart', args=(self.session.code,))
        worker_id = 'WORKER_ID01'
        assignment_id = 'ASSIGNMENT_ID01'
        response = self.browser.get(
            url,
            data={
                'assignmentId': assignment_id,
                'workerId': worker_id
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        mocked_client.assign_qualification.assert_called()
        p_visitor = Participant.objects.get(
            session=self.session,
            visited=True
        )
        p_non_visitor = Participant.objects.filter(
            session=self.session,
            visited=False
        )[0]

        self.assertTrue(p_visitor.mturk_worker_id == worker_id)
        self.assertTrue(p_visitor.mturk_assignment_id == assignment_id)
        self.assertTrue(p_non_visitor.mturk_worker_id is None)
        self.assertTrue(p_non_visitor.mturk_assignment_id is None)

    def test_mturk_landing_page(self):
        url = reverse('MTurkLandingPage', args=(self.session.code,))
        assignment_id = 'ASSIGNMENT_ID01'
        worker_id = 'WORKER_ID01'
        response = self.browser.get(
            url,
            data={
                'assignmentId': assignment_id,
                'workerId': worker_id
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)


class TestPayMTurk(ChannelLiveServerTestCase):

    def setUp(self):
        num_participants = 6
        # create a session
        call_command('create_session', 'mturk', str(num_participants))
        self.session = Session.objects.get()
        self.session.mturk_HITId = 'FAKEHITID'
        self.session.save()
        self.browser = OTreePhantomBrowser(self.live_server_url)
        self.participants = self.session.get_participants()

    # easier to mock these methods than having to think about points conversion
    @mock.patch.object(Participant, 'payoff_in_real_world_currency')
    @mock.patch.object(Participant, 'payoff_plus_participation_fee')
    @mock.patch('otree.views.mturk.get_mturk_client')
    def test_pay_mturk(
            self, mock_get_mturk_client,
            mock_payoff_plus_participation_fee,
            mock_payoff_in_real_world_currency
    ):
        mocked_client = mock_get_mturk_client()#.return_value

        num_participants_to_pay = 4
        bonus_per_participant = 0.2
        total_pay_per_participant = 0.6


        mock_payoff_in_real_world_currency.return_value = RealWorldCurrency(bonus_per_participant)
        mock_payoff_plus_participation_fee.return_value = RealWorldCurrency(total_pay_per_participant)


        # simulate workers arriving from MTurk by assigning bogus worker IDs
        # and assignment IDs
        for (i, p) in enumerate(self.participants):
            p.mturk_worker_id = str(i)
            p.mturk_assignment_id = str(i)
            p.save()

        # mock the result set, so that when the view queries MTurk to see
        # who is submitted, it returns a list of MTurk workers
        assignments = [
            {'WorkerId': p.mturk_worker_id, 'AssignmentStatus': 'Submitted'}
            for
            p in self.participants[:num_participants_to_pay]
        ]

        mocked_client.list_assignments_for_hit.return_value = assignments

        # basically, all this tests is that it doesn't crash
        #session = Session.objects.get()
        #self.assertEqual(session.code, self.session.code)
        url = reverse('MTurkSessionPayments', args=[self.session.code])
        br = self.browser
        br.go(url)

        with open('MTurkSessionPayments.html', 'wb') as f:
            f.write(br.html.encode('utf-8'))
        br.screenshot('MTurkSessionPayments')
        br.find_by_css('[name="workers"][value="1"]').check()
        br.find_by_css('[name="workers"][value="2"]').check()
        button = br.find_by_css('button.pay')

        self.assertEqual(button.text, 'Pay via MTurk ($1.20)')
        button.click()

        confirm_button = br.find_by_id('pay-confirm-button')
        confirm_button.click()

        calls = mocked_client.approve_assignment.call_args_list
        for asst_id in ['1', '2']:
            mocked_client.approve_assignment.assert_called_with(
                AssignmentId=asst_id)

        calls = mocked_client.send_bonus.call_args_list
        self.assertEqual(len(calls), 2)

        for call in calls:
            kwargs = calls[1]
            self.assertEqual(kwargs['BonusAmount'], '0.20')
            # because our bogus worker ID is the same as our bogus assignment ID
            self.assertEqual(kwargs['WorkerId'], kwargs['AssignmentId'])

        # after submitting, oTree redirects to the payments page
        br.find_by_css('[name="workers"][value="3"]').check()
        br.find_by_css('[name="workers"][value="4"]').check()
        button = br.find_by_css('button.reject')
        button.click()

        reject_confirm_button = br.find_by_id('reject-confirm-button')
        reject_confirm_button.click()

        calls = mocked_client.reject_assignment.call_args_list
        self.assertEqual(len(calls), 2)
        for asst_id in ['3', '4']:
            mocked_client.reject_assignment.assert_called_with(
                AssignmentId=asst_id, RequesterFeedback='')


class Foo:
    def f(self):
        print('***********should not execute')
        return 'In Foo.f'

def foo_test():
    return Foo().f()

def function_to_mock_local():
    raise AssertionError('**********should not execute')



'''
    @mock.patch.object(Foo, 'f')
    def test_foo(self, patched_f):
        patched_f.return_value = 'in test case'
        self.assertEqual(foo_test(), 'in test case')
'''

class TestFoo(TestCase):

    @mock.patch('otree.views.mturk.function_to_mock')
    def test_foo_3(self, patched):
        function_to_mock()


#class TestFoo(ChannelLiveServerTestCase):
class TestFoo(TestCase):

    @mock.patch('otree.views.mturk.function_to_mock')
    def test_foo_3(self, patched):
        function_to_mock()

    @mock.patch('tests.test_mturk.function_to_mock_local')
    def test_foo_2(self, patched):
        function_to_mock_local()
