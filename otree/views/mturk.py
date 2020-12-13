import contextlib
import json
import logging
from collections import defaultdict, namedtuple
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Union, Optional
from starlette.responses import Response, RedirectResponse
import otree.views.cbv
from otree import settings
from starlette.requests import Request
from otree.database import values_flat, db
import otree
from otree.models import Session, Participant
from otree.views.cbv import AdminSessionPage
from .cbv import enqueue_admin_message
from otree.templating import ibis_loader


try:
    import boto3
except ImportError:
    boto3 = None

logger = logging.getLogger('otree')


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
        enqueue_admin_message('error', repr(exc))


def in_public_domain(request: Request):
    """This method validates if oTree are published on a public domain
    because mturk need it

    """
    host = request.url.hostname.lower()
    if ":" in host:
        host = host.split(":", 1)[0]
    if host in ["localhost", '127.0.0.1']:
        return False
    # IPy had a compat problem with py 3.8.
    # in the future, could move some IPy code here.
    return True


class MTurkCreateHIT(AdminSessionPage):

    # make these class attributes so they can be mocked
    aws_keys_exist = bool(
        getattr(settings, 'AWS_ACCESS_KEY_ID', None)
        and getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
    )
    boto3_installed = bool(boto3)

    def vars_for_template(self):
        session = self.session

        mturk_settings = session.config['mturk_hit_settings']

        is_new_format = 'template' in mturk_settings
        is_usd = settings.REAL_WORLD_CURRENCY_CODE == 'USD'
        mturk_ready = (
            self.aws_keys_exist and self.boto3_installed and is_new_format and is_usd
        )

        return dict(
            mturk_settings=mturk_settings,
            participation_fee=session.config['participation_fee'],
            mturk_num_workers=session.mturk_num_workers(),
            mturk_ready=mturk_ready,
            boto3_installed=self.boto3_installed,
            aws_keys_exist=self.aws_keys_exist,
            is_new_format=is_new_format,
            is_usd=is_usd,
        )

    def post(self, request, code):
        session = self.session
        use_sandbox = bool(self.get_post_data().get('use_sandbox'))
        if not in_public_domain(request) and not use_sandbox:
            msg = 'oTree must run on a public domain for Mechanical Turk'
            return Response(msg)
        mturk_settings = MTurkSettings(**session.config['mturk_hit_settings'])

        start_url = self.request.url_for('MTurkStart', code=session.code)

        keywords = mturk_settings.keywords
        if isinstance(keywords, (list, tuple)):
            keywords = ', '.join(keywords)

        html_question = ibis_loader('otree/MTurkHTMLQuestion.html').render(
            user_template=mturk_settings.template,
            frame_height=mturk_settings.frame_height,
            start_url=start_url,
        )

        mturk_hit_parameters = {
            'Title': mturk_settings.title,
            'Description': mturk_settings.description,
            'Keywords': keywords,
            'MaxAssignments': session.mturk_num_workers(),
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
            session.mturk_qual_id = mturk_settings.grant_qualification_id or ''

        return self.redirect('MTurkCreateHIT', code=session.code)


Assignment = namedtuple(
    'Assignment', ['worker_id', 'assignment_id', 'status', 'answer']
)


def get_all_assignments(mturk_client, hit_id) -> List[Assignment]:
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
        for d in response['Assignments']:
            assignments.append(
                Assignment(
                    worker_id=d['WorkerId'],
                    assignment_id=d['AssignmentId'],
                    status=d['AssignmentStatus'],
                    answer=d['Answer'],
                )
            )
        args['NextToken'] = response['NextToken']

    return assignments


def get_workers_by_status(
    all_assignments: List[Assignment],
) -> Dict[str, List[Assignment]]:
    workers_by_status = defaultdict(list)
    for assignment in all_assignments:
        workers_by_status[assignment.status].append(assignment.worker_id)
    return workers_by_status


class MTurkSessionPayments(AdminSessionPage):
    def vars_for_template(self):
        session = self.session
        if not session.mturk_HITId:
            return dict(published=False)

        with MTurkClient(
            use_sandbox=session.mturk_use_sandbox, request=self.request
        ) as mturk_client:
            all_assignments = get_all_assignments(mturk_client, session.mturk_HITId)

            # auto-reject logic
            assignment_ids_in_db = values_flat(
                session.pp_set.filter(Participant.mturk_assignment_id != None),
                'mturk_assignment_id',
            )

            submitted_assignment_ids = [
                a.assignment_id for a in all_assignments if a.status == 'Submitted'
            ]

            auto_rejects = set(submitted_assignment_ids) - set(assignment_ids_in_db)

            for assignment_id in auto_rejects:
                mturk_client.reject_assignment(
                    AssignmentId=assignment_id,
                    RequesterFeedback='Auto-rejecting because this assignment was not found in our database.',
                )

        workers_by_status = get_workers_by_status(all_assignments)

        def get_participants_by_status(status):
            return list(
                session.pp_set.filter(
                    Participant.mturk_worker_id.in_(workers_by_status[status])
                )
            )

        participants_approved = get_participants_by_status('Approved')
        participants_rejected = get_participants_by_status('Rejected')
        participants_not_reviewed = get_participants_by_status('Submitted')

        for lst in [
            participants_not_reviewed,
            participants_approved,
            participants_rejected,
        ]:
            add_answers(lst, all_assignments)

        return dict(
            published=True,
            participants_approved=participants_approved,
            participants_rejected=participants_rejected,
            participants_not_reviewed=participants_not_reviewed,
            participation_fee=session.config['participation_fee'],
            auto_rejects=auto_rejects,
        )


def get_completion_code(xml: str) -> str:
    if not xml:
        return ''
    # move inside function because it adds 0.03s to startup time
    from xml.etree import ElementTree

    root = ElementTree.fromstring(xml)
    for ans in root:
        if ans[0].text == 'taskAnswers':
            answer_data = json.loads(ans[1].text)
            try:
                return answer_data[0]['completion_code']
            except:
                return ''
    return ''


def add_answers(participants: List[Participant], all_assignments: List[Assignment]):
    answers = {}
    for assignment in all_assignments:
        answers[assignment.worker_id] = assignment.answer
    for p in participants:
        p._is_frozen = False
        p.mturk_answers_formatted = get_completion_code(answers[p.mturk_worker_id])


class PayMTurk(AdminSessionPage):
    """only POST"""

    url_pattern = '/PayMTurk/{code}'

    def post(self, request, code):
        session = db.get_or_404(Session, code=code)
        successful_payments = 0
        failed_payments = 0
        post_data = self.get_post_data()
        mturk_client = get_mturk_client(use_sandbox=session.mturk_use_sandbox)
        payment_page_response = self.redirect('MTurkSessionPayments', code=session.code)
        # use worker ID instead of assignment ID. Because 2 workers can have
        # the same assignment (if 1 starts it then returns it). we can't really
        # block that.
        # however, we can ensure that 1 worker does not get 2 assignments,
        # by enforcing that the same worker is always assigned to the same participant.
        participants = session.pp_set.filter(
            Participant.mturk_worker_id.in_(post_data.getlist('workers'))
        )

        for p in participants:
            # need the try/except so that we try to pay the rest of the participants
            payoff = p.payoff_in_real_world_currency()

            try:
                if payoff > 0:
                    mturk_client.send_bonus(
                        WorkerId=p.mturk_worker_id,
                        AssignmentId=p.mturk_assignment_id,
                        BonusAmount='{0:.2f}'.format(Decimal(payoff)),
                        # prevent duplicate payments
                        UniqueRequestToken='{}_{}'.format(
                            p.mturk_worker_id, p.mturk_assignment_id
                        ),
                        # this field is required.
                        Reason='Thank you',
                    )
                # approve assignment should happen AFTER bonus, so that if bonus fails,
                # the user will still show up in assignments_not_reviewed.
                # worst case is that bonus succeeds but approval fails.
                # in that case, exception will be raised on send_bonus because of UniqueRequestToken.
                # but that's OK, then you can just unselect that participant and pay the others.
                mturk_client.approve_assignment(AssignmentId=p.mturk_assignment_id)
                successful_payments += 1
            except Exception as e:
                msg = (
                    'Could not pay {} because of an error communicating '
                    'with MTurk: {}'.format(p._numeric_label(), str(e))
                )
                enqueue_admin_message('error', msg)
                logger.error(msg)
                failed_payments += 1
                if failed_payments > 10:
                    return payment_page_response
        msg = 'Successfully made {} payments.'.format(successful_payments)
        if failed_payments > 0:
            msg += ' {} payments failed.'.format(failed_payments)
            enqueue_admin_message('warning', msg)
        else:
            enqueue_admin_message('success', msg)
        return payment_page_response


class RejectMTurk(AdminSessionPage):
    """POST only"""

    url_pattern = '/RejectMTurk/{code}'

    def post(self, request, code):
        session = db.get_or_404(Session, code=code)
        with MTurkClient(
            use_sandbox=session.mturk_use_sandbox, request=request
        ) as mturk_client:
            for p in session.pp_set.filter(
                Participant.mturk_worker_id.in_(self.get_post_data().getlist('workers'))
            ):
                mturk_client.reject_assignment(
                    AssignmentId=p.mturk_assignment_id,
                    # The boto3 docs say this param is optional, but if I omit it, I get:
                    # An error occurred (ValidationException) when calling the RejectAssignment operation:
                    # 1 validation error detected: Value null at 'requesterFeedback'
                    # failed to satisfy constraint: Member must not be null
                    RequesterFeedback='',
                )

            enqueue_admin_message('success', "Rejected the selected assignments")
        return self.redirect('MTurkSessionPayments', code=code)


class MTurkExpireHIT(AdminSessionPage):
    """only POST"""

    url_pattern = '/MTurkExpireHIT/{code}'

    def post(self, request, code):
        session = db.get_or_404(Session, code=code)
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
        # don't need a message because the MTurkCreateHIT page will
        # statically say the HIT has expired.
        return self.redirect('MTurkCreateHIT', code=code)
