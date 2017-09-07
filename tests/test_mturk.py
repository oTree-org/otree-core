from collections import namedtuple
from django.core.management import call_command
from django.core.urlresolvers import reverse
from otree.common import RealWorldCurrency
from otree.models import Session, Participant
from otree.views.mturk import MTurkClient
import django.test.client
from unittest import mock
from unittest.mock import MagicMock
from .utils import TestCase
from django.test import override_settings, LiveServerTestCase
from tests.utils import OTreePhantomBrowser

from otree.views.mturk import get_mturk_client


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
        mocked_client = mock_get_mturk_client.return_value

        url = reverse('MTurkStart', args=(self.session.code,))
        # needs to start with 'A'
        worker_id = 'AWORKERID1'
        assignment_id = 'ASSIGNMENTID1'
        response = self.browser.get(
            url,
            data={
                'assignmentId': assignment_id,
                'workerId': worker_id
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        # worker returns the assignment, accepts another assignment
        assignment_id2 = 'ASSIGNMENTID2'
        response = self.browser.get(
            url,
            data={
                'assignmentId': assignment_id2,
                'workerId': worker_id
            },
            follow=True
        )

        mocked_client.associate_qualification_with_worker.assert_called()

        # should be only 1
        p_visitor = Participant.objects.get(
            session=self.session,
            visited=True
        )
        p_non_visitor = Participant.objects.filter(
            session=self.session,
            visited=False
        )[0]

        self.assertEqual(p_visitor.mturk_worker_id, worker_id)
        self.assertEqual(p_visitor.mturk_assignment_id, assignment_id2)
        self.assertEqual(p_non_visitor.mturk_worker_id, None)
        self.assertEqual(p_non_visitor.mturk_assignment_id, None)

    @mock.patch('otree.views.mturk.get_mturk_client')
    def test_mturk_preview(self, mock_get_mturk_client):
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



class TestPayMTurk(LiveServerTestCase):

    '''
    Use LiveServerTestCase instead of ChannelLiveServerTestCase, because
    I need to use mocks, which are not possible with ChannelLiveServerTestCase
    because it uses a separate process
    '''

    def setUp(self):
        num_participants = 6
        # create a session
        call_command('create_session', 'mturk', str(num_participants))
        self.session = Session.objects.get()
        self.session.mturk_HITId = 'FAKEHITID'
        self.session.save()
        self.browser = OTreePhantomBrowser(live_server_url=self.live_server_url)
        self.participants = list(self.session.get_participants())

    # so we don't have to worry about points conversion.
    @override_settings(USE_POINTS=False)
    @mock.patch('otree.views.mturk.get_mturk_client')
    def test_pay(self, mock_get_mturk_client):

        mocked_client = mock_get_mturk_client()

        bonus_per_participant = 0.2
        self.assertEqual(self.session.config['participation_fee'], 0.4)
        total_pay_per_participant = 0.6

        # simulate workers arriving from MTurk by assigning bogus worker IDs
        # and assignment IDs
        for p in self.participants:
            p.mturk_assignment_id = p.mturk_worker_id = str(p.id_in_session)
            p.payoff = bonus_per_participant
            p.save()

        # mock the result set, so that when the view queries MTurk to see
        # who is submitted, it returns a list of MTurk workers

        def list_assignments_for_hit(**kwargs):
            # don't paginate
            if 'NextToken' in kwargs:
                return {'Assignments': []}
            return {
                'NextToken': 'foo',
                'Assignments': [
                    {'WorkerId': p.mturk_worker_id, 'AssignmentStatus': 'Submitted'}
                    # simulate that not everyone submitted
                    for p in self.participants[:-2]
                ]
            }

        mocked_client.list_assignments_for_hit = list_assignments_for_hit

        url = reverse('MTurkSessionPayments', args=[self.session.code])
        br = self.browser
        br.go(url)

        br.find_by_css('[name="workers"][value="1"]').check()
        br.find_by_css('[name="workers"][value="2"]').check()

        button = br.find_by_css('button#pay')
        self.assertEqual(button.text, 'Pay via MTurk ($1.20)')
        button.click()

        confirm_button = br.find_by_id('pay-confirm-button')
        confirm_button.click()

        calls = mocked_client.approve_assignment.call_args_list
        for asst_id in ['1', '2']:
            mocked_client.approve_assignment.assert_any_call(
                AssignmentId=asst_id)

        calls = mocked_client.send_bonus.call_args_list
        self.assertEqual(len(calls), 2)

        for call in calls:
            kwargs = call[1]
            self.assertEqual(kwargs['BonusAmount'], '0.20')
            # because our bogus worker ID is the same as our bogus assignment ID
            self.assertEqual(kwargs['WorkerId'], kwargs['AssignmentId'])

        # after submitting, oTree redirects to the payments page
        br.find_by_css('[name="workers"][value="3"]').check()
        br.find_by_css('[name="workers"][value="4"]').check()

        button = br.find_by_css('button#reject')
        button.click()
        reject_confirm_button = br.find_by_id('reject-confirm-button')
        reject_confirm_button.click()

        calls = mocked_client.reject_assignment.call_args_list
        self.assertEqual(len(calls), 2)
        for asst_id in ['3', '4']:
            mocked_client.reject_assignment.assert_any_call(
                AssignmentId=asst_id, RequesterFeedback='')
