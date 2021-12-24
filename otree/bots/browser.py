import logging
from otree.common import rng
from collections import OrderedDict
from typing import Dict
from otree.models import Session
from .bot import ParticipantBot, Submission
from .runner import make_bots
import otree.channels.utils as channel_utils


# if you are testing all configs from the CLI browser bot launcher,
# and each app has multiple cases, it's possible to end up with many
# bots in the history.
# usually this wouldn't matter,
# but timeoutworker may try to load the pages after they have been completed
# (it will POST then get redirected to GET)

SESSIONS_PRUNE_LIMIT = 80

logger = logging.getLogger('otree.test.browser_bots')


class BadRequestError(Exception):

    pass


PARTICIPANT_NOT_IN_BOTWORKER_MSG = (
    "Bot for Participant {participant_code} not loaded. "
    "This can happen for several reasons: "
    "(1) You restarted the server after creating the session "
    "(2) The bots expired "
    "(the server stores bots for "
    "only the most recent {prune_limit} sessions)."
)


class BotWorker:
    def __init__(self):
        self.participants_by_session = OrderedDict()
        self.browser_bots: Dict[str, ParticipantBot] = {}
        self.queued_post_data: Dict[str, Submission] = {}

    def initialize_session(self, session_pk, case_number):
        self.prune()
        self.participants_by_session[session_pk] = []

        session = Session.objects_get(id=session_pk)
        if case_number is None:
            # choose one randomly
            from otree.session import SessionConfig

            config = SessionConfig(session.config)
            num_cases = config.get_num_bot_cases()
            case_number = rng.choice(range(num_cases))

        bots = make_bots(
            session_pk=session_pk, case_number=case_number, use_browser_bots=True
        )
        for bot in bots:
            self.participants_by_session[session_pk].append(bot.participant_code)
            self.browser_bots[bot.participant_code] = bot

    def prune(self):
        '''to avoid memory leaks'''
        if len(self.participants_by_session) > SESSIONS_PRUNE_LIMIT:
            _, p_codes = self.participants_by_session.popitem(last=False)
            for participant_code in p_codes:
                self.browser_bots.pop(participant_code, None)

    def get_bot(self, participant_code):
        try:
            return self.browser_bots[participant_code]
        except KeyError:
            msg = PARTICIPANT_NOT_IN_BOTWORKER_MSG.format(
                participant_code=participant_code, prune_limit=SESSIONS_PRUNE_LIMIT
            )
            raise BadRequestError(msg)

    def enqueue_next_post_data(self, participant_code) -> bool:
        qpd = self.queued_post_data
        if participant_code in qpd:
            # already queued up, maybe the page got refreshed somehow
            return True
        bot = self.get_bot(participant_code)
        try:
            qpd[participant_code] = bot.get_next_submit()
        except StopIteration:
            # don't prune it because can cause flakiness if
            # there are other GET requests coming in. it will be pruned
            # when new sessions are created anyway.

            # return None instead of raising an exception, because
            # None can easily be serialized in Redis. Means the code can be
            # basically the same for Redis and non-Redis
            return False
        else:
            return True

    def pop_enqueued_post_data(self, participant_code) -> Dict:
        # because we are returning it through Redis, need to pop it
        # here
        submission = self.queued_post_data.pop(participant_code)
        return submission.post_data

    def set_attributes(self, participant_code, request_path, html):
        bot = self.get_bot(participant_code)
        # so that any asserts in the PlayerBot work.
        bot.path = request_path
        bot.html = html


# global variable that holds the browser bot worker instance in memory
browser_bot_worker: BotWorker = None


def set_attributes(**kwargs):
    browser_bot_worker.set_attributes(**kwargs)


def enqueue_next_post_data(**kwargs) -> bool:
    return browser_bot_worker.enqueue_next_post_data(**kwargs)


def pop_enqueued_post_data(**kwargs) -> dict:
    return browser_bot_worker.pop_enqueued_post_data(**kwargs)


def initialize_session(**kwargs):
    return browser_bot_worker.initialize_session(**kwargs)


def send_completion_message(*, session_code, participant_code):
    group_name = channel_utils.browser_bots_launcher_group(session_code)

    channel_utils.sync_group_send(
        group=group_name, data=dict(participant_code=participant_code),
    )
