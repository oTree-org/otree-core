import json
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Union, Optional
import logging
from xml.etree import ElementTree

from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseServerError
from django.shortcuts import get_object_or_404

from django.template.loader import render_to_string

import vanilla

try:
    import boto3
except ImportError:
    boto3 = None

import otree

from otree.views.abstract import AdminSessionPageMixin

from otree.models_concrete import add_time_spent_waiting
from otree.models import Session, Participant
from decimal import Decimal
from django.shortcuts import redirect

logger = logging.getLogger('otree')

import contextlib
from dataclasses import dataclass


@dataclass
class MTurkSettings:
    keywords: Union[str, list]
    title: str
    description: str
    frame_height: int
    template: str
    minutes_allotted_per_assignment: int
    expiration_hours: float
    qualification_requirements: List
    grant_qualification_id: Optional[str] = None


def get_mturk_client(*, use_sandbox=True):
    if use_sandbox:
        endpoint_url = 'https://mturk-requester-sandbox.us-east-1.amazonaws.com'
    else:
        endpoint_url = 'https://mturk-requester.us-east-1.amazonaws.com'
    return boto3.client(
        'mturk',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=endpoint_url,
        # if I specify endpoint_url without region_name, it complains
        region_name='us-east-1',
    )


@contextlib.contextmanager
def MTurkClient(*, use_sandbox=True, request):
    '''Alternative to get_mturk_client, for when we need exception handling
    in admin views, we should pass it, so that we can show the user the message
    without crashing.
    for participant-facing views and commandline tools, should use get_mturk_client.
    '''
    try:
        yield get_mturk_client(use_sandbox=use_sandbox)
    except Exception as exc:
        logger.error('MTurk error', exc_info=True)
        messages.error(request, str(exc), extra_tags='safe')


def get_all_assignments(mturk_client, hit_id):
    # Accumulate all relevant assignments, one page of results at
    # a time.
    assignments = []

    args = dict(
        HITId=hit_id,
        # i think 100 is the max page size
        MaxResults=100,
        AssignmentStatuses=['Submitted', 'Approved', 'Rejected'],
    )

    while True:
        response = mturk_client.list_assignments_for_hit(**args)
        if not response['Assignments']:
            break
        assignments.extend(response['Assignments'])
        args['NextToken'] = response['NextToken']

    return assignments


def in_public_domain(request):
    """This method validates if oTree are published on a public domain
    because mturk need it

    """
    host = request.get_host().lower()
    if ":" in host:
        host = host.split(":", 1)[0]
    if host in ["localhost", '127.0.0.1']:
        return False
    # IPy had a compat problem with py 3.8.
    # in the future, could move some IPy code here.
    return True


class MTurkCreateHIT(AdminSessionPageMixin, vanilla.FormView):

    # make these class attributes so they can be mocked
    aws_keys_exist = bool(
        getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        and getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
    )
    boto3_installed = bool(boto3)

    def get(self, request):

        session = self.session

        mturk_settings = session.config['mturk_hit_settings']

        is_new_format = 'template' in mturk_settings
        is_usd = settings.REAL_WORLD_CURRENCY_CODE == 'USD'
        mturk_ready = (
            self.aws_keys_exist and self.boto3_installed and is_new_format and is_usd
        )

        context = self.get_context_data(
            mturk_settings=mturk_settings,
            participation_fee=session.config['participation_fee'],
            mturk_num_participants=session.mturk_num_participants,
            mturk_ready=mturk_ready,
            boto3_installed=self.boto3_installed,
            aws_keys_exist=self.aws_keys_exist,
            is_new_format=is_new_format,
            is_usd=is_usd,
        )

        return self.render_to_response(context)

    def post(self, request):
        session = self.session
        use_sandbox = bool(request.POST.get('use_sandbox'))
        if not in_public_domain(request) and not use_sandbox:
            msg = (
                '<h1>Error: '
                'oTree must run on a public domain for Mechanical Turk'
                '</h1>'
            )
            return HttpResponseServerError(msg)
        mturk_settings = MTurkSettings(**session.config['mturk_hit_settings'])

        start_url = self.request.build_absolute_uri(
            reverse('MTurkStart', args=(session.code,))
        )

        keywords = mturk_settings.keywords
        if isinstance(keywords, (list, tuple)):
            keywords = ', '.join(keywords)

        html_question = render_to_string(
            'otree/MTurkHTMLQuestion.html',
            context=dict(
                user_template=mturk_settings.template,
                frame_height=mturk_settings.frame_height,
                start_url=start_url,
            ),
        )

        mturk_hit_parameters = {
            'Title': mturk_settings.title,
            'Description': mturk_settings.description,
            'Keywords': keywords,
            'MaxAssignments': session.mturk_num_participants,
            'Reward': str(float(session.config['participation_fee'])),
            'AssignmentDurationInSeconds': 60
            * mturk_settings.minutes_allotted_per_assignment,
            'LifetimeInSeconds': int(60 * 60 * mturk_settings.expiration_hours),
            # prevent duplicate HITs
            'UniqueRequestToken': 'otree_{}'.format(session.code),
            'Question': html_question,
        }

        if not use_sandbox:
            # drop requirements checks in sandbox mode.
            mturk_hit_parameters[
                'QualificationRequirements'
            ] = mturk_settings.qualification_requirements

        with MTurkClient(use_sandbox=use_sandbox, request=request) as mturk_client:

            hit = mturk_client.create_hit(**mturk_hit_parameters)['HIT']

            session.mturk_HITId = hit['HITId']
            session.mturk_HITGroupId = hit['HITGroupId']
            session.mturk_use_sandbox = use_sandbox
            session.mturk_expiration = hit['Expiration'].timestamp()
            session.save()

        return redirect('MTurkCreateHIT', session.code)


class MTurkSessionPayments(AdminSessionPageMixin, vanilla.TemplateView):
    def vars_for_template(self):
        session = self.session
        published = bool(session.mturk_HITId)
        if not published:
            return dict(published=False)
        with MTurkClient(
            use_sandbox=session.mturk_use_sandbox, request=self.request
        ) as mturk_client:
            all_assignments = get_all_assignments(mturk_client, session.mturk_HITId)

        workers_by_status = get_workers_by_status(all_assignments)

        participants_not_reviewed = session.participant_set.filter(
            mturk_worker_id__in=workers_by_status['Submitted']
        )
        participants_approved = session.participant_set.filter(
            mturk_worker_id__in=workers_by_status['Approved']
        )
        participants_rejected = session.participant_set.filter(
            mturk_worker_id__in=workers_by_status['Rejected']
        )

        add_time_spent_waiting(participants_not_reviewed)
        add_answers(participants_not_reviewed, all_assignments)

        return dict(
            published=True,
            participants_approved=participants_approved,
            participants_rejected=participants_rejected,
            participants_not_reviewed=participants_not_reviewed,
            participation_fee=session.config['participation_fee'],
        )


def get_workers_by_status(all_assignments) -> Dict[str, List[str]]:
    workers_by_status = defaultdict(list)
    for assignment in all_assignments:
        workers_by_status[assignment['AssignmentStatus']].append(assignment['WorkerId'])
    return workers_by_status


def get_completion_code(xml: str) -> str:
    if not xml:
        return ''
    root = ElementTree.fromstring(xml)
    for ans in root:
        if ans[0].text == 'taskAnswers':
            answer_data = json.loads(ans[1].text)
            try:
                return answer_data[0]['completion_code']
            except:
                return ''
    return ''


def add_answers(participants: List[Participant], all_assignments: List[dict]):
    answers = {}
    for assignment in all_assignments:
        answers[assignment['WorkerId']] = assignment['Answer']
    for p in participants:
        p.mturk_answers_formatted = get_completion_code(answers[p.mturk_worker_id])


class PayMTurk(vanilla.View):
    url_pattern = r'^PayMTurk/(?P<session_code>[a-z0-9]+)/$'

    def post(self, request, session_code):
        session = get_object_or_404(otree.models.Session, code=session_code)
        successful_payments = 0
        failed_payments = 0
        mturk_client = get_mturk_client(use_sandbox=session.mturk_use_sandbox)
        payment_page_response = redirect('MTurkSessionPayments', session.code)
        # use worker ID instead of assignment ID. Because 2 workers can have
        # the same assignment (if 1 starts it then returns it). we can't really
        # block that.
        # however, we can ensure that 1 worker does not get 2 assignments,
        # by enforcing that the same worker is always assigned to the same participant.
        participants = session.participant_set.filter(
            mturk_worker_id__in=request.POST.getlist('workers')
        )

        # we require only that there's enough for paying the bonuses,
        # because the participation fee (reward) is already deducted from
        # available balance and held in escrow. (see forum post from 2019-06-19)
        # The 1.2 is because of the 20% surcharge to bonuses, as described here:
        # https://requester.mturk.com/pricing
        required_balance = Decimal(
            sum(p.payoff_in_real_world_currency() for p in participants) * 1.2
        )

        available_balance = Decimal(
            mturk_client.get_account_balance()['AvailableBalance']
        )

        if available_balance < required_balance:
            msg = (
                f'Insufficient balance: you have ${available_balance:.2f}, '
                f'but paying the selected participants costs ${required_balance:.2f}.'
            )
            messages.error(request, msg)
            return payment_page_response

        for p in participants:
            # need the try/except so that we try to pay the rest of the participants
            payoff = p.payoff_in_real_world_currency()

            try:
                # approve assignment
                mturk_client.approve_assignment(AssignmentId=p.mturk_assignment_id)
                if payoff > 0:
                    mturk_client.send_bonus(
                        WorkerId=p.mturk_worker_id,
                        AssignmentId=p.mturk_assignment_id,
                        BonusAmount='{0:.2f}'.format(Decimal(payoff)),
                        # prevent duplicate payments
                        UniqueRequestToken='{}_{}'.format(
                            p.mturk_worker_id, p.mturk_assignment_id
                        ),
                        # although the Boto documentation doesn't say so,
                        # this field is required. A user reported:
                        # "Value null at 'reason' failed to satisfy constraint:
                        # Member must not be null."
                        Reason='Thank you',
                    )
                successful_payments += 1
            except Exception as e:
                msg = (
                    'Could not pay {} because of an error communicating '
                    'with MTurk: {}'.format(p._id_in_session(), str(e))
                )
                messages.error(request, msg)
                logger.error(msg)
                failed_payments += 1
        msg = 'Successfully made {} payments.'.format(successful_payments)
        if failed_payments > 0:
            msg += ' {} payments failed.'.format(failed_payments)
            messages.warning(request, msg)
        else:
            messages.success(request, msg)
        return payment_page_response


class RejectMTurk(vanilla.View):
    url_pattern = r'^RejectMTurk/(?P<session_code>[a-z0-9]+)/$'

    def post(self, request, session_code):
        session = get_object_or_404(Session, code=session_code)
        with MTurkClient(
            use_sandbox=session.mturk_use_sandbox, request=request
        ) as mturk_client:
            for p in session.participant_set.filter(
                mturk_worker_id__in=request.POST.getlist('workers')
            ):
                mturk_client.reject_assignment(
                    AssignmentId=p.mturk_assignment_id,
                    # The boto3 docs say this param is optional, but if I omit it, I get:
                    # An error occurred (ValidationException) when calling the RejectAssignment operation:
                    # 1 validation error detected: Value null at 'requesterFeedback'
                    # failed to satisfy constraint: Member must not be null
                    RequesterFeedback='',
                )

            messages.success(
                request, "You successfully rejected " "selected assignments"
            )
        return redirect('MTurkSessionPayments', session_code)


class MTurkExpireHIT(vanilla.View):
    url_pattern = r'^MTurkExpireHIT/(?P<session_code>[a-z0-9]+)/$'

    def post(self, request, session_code):
        session = get_object_or_404(Session, code=session_code)
        with MTurkClient(
            use_sandbox=session.mturk_use_sandbox, request=request
        ) as mturk_client:
            expiration = datetime(2015, 1, 1)
            mturk_client.update_expiration_for_hit(
                HITId=session.mturk_HITId,
                # If you update it to a time in the past,
                # the HIT will be immediately expired.
                ExpireAt=expiration,
            )
            session.mturk_expiration = expiration.timestamp()
            session.save()

            # don't need a message because the MTurkCreateHIT page will
            # statically say the HIT has expired.

        return redirect('MTurkCreateHIT', session.code)
