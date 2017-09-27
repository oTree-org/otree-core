import json
import threading
import logging
from collections import OrderedDict

import channels
import traceback

import otree.common_internal
from otree.models.participant import Participant
from otree.common_internal import get_redis_conn

from .runner import make_bots
from .bot import ParticipantBot
import random
from otree.models_concrete import ParticipantToPlayerLookup
from otree.models import Session

REDIS_KEY_PREFIX = 'otree-bots'

# if you are testing all configs from the CLI browser bot launcher,
# and each app has multiple cases, it's possible to end up with many
# bots in the history.
# usually this wouldn't matter,
# but timeoutworker may try to load the pages after they have been completed
# (it will POST then get redirected to GET)
SESSIONS_PRUNE_LIMIT = 80

# global variable that holds the browser bot worker instance in memory
browser_bot_worker = None  # type: Worker

# these locks are only necessary when using runserver
# because then the botworker stuff is done by one of the 4 worker threads.
prepare_submit_lock = threading.Lock()
add_or_remove_bot_lock = threading.Lock()

logger = logging.getLogger('otree.test.browser_bots')


class Worker(object):
    def __init__(self, redis_conn=None):
        self.redis_conn = redis_conn
        self.participants_by_session = OrderedDict()
        self.browser_bots = {}
        self.prepared_submits = {}

    def initialize_session(self, session_pk, case_number):
        self.prune()
        self.participants_by_session[session_pk] = []

        session = Session.objects.get(pk=session_pk)
        if case_number is None:
            # choose one randomly
            from otree.session import SessionConfig
            config = SessionConfig(session.config)
            num_cases = config.get_num_bot_cases()
            case_number = random.choice(range(num_cases))

        bots = make_bots(
            session_pk=session_pk, case_number=case_number, use_browser_bots=True
        )
        for bot in bots:
            self.participants_by_session[session_pk].append(
                bot.participant_code)
            self.browser_bots[bot.participant_code] = bot
        return {'ok': True}

    def get_method(self, command_name):
        commands = {
            'prepare_next_submit': self.prepare_next_submit,
            'consume_next_submit': self.consume_next_submit,
            'initialize_session': self.initialize_session,
            'clear_all': self.clear_all,
            'ping': self.ping,
        }

        return commands[command_name]

    def prune(self):
        '''to avoid memory leaks'''
        with add_or_remove_bot_lock:
            if len(self.participants_by_session) > SESSIONS_PRUNE_LIMIT:
                _, p_codes = self.participants_by_session.popitem(last=False)
                for participant_code in p_codes:
                    self.browser_bots.pop(participant_code, None)

    def clear_all(self):
        self.browser_bots.clear()

    def consume_next_submit(self, participant_code):
        submission = self.prepared_submits.pop(participant_code)
        # maybe was popped in prepare_next_submit
        submission.pop('page_class', None)
        return submission

    def prepare_next_submit(self, participant_code, path, html):

        try:
            bot = self.browser_bots[participant_code]
        except KeyError:
            return {
                'request_error': (
                    "Participant {} not loaded in botworker. "
                    "This can happen for several reasons: "
                    "(1) You are running multiple botworkers "
                    "(2) You restarted the botworker after creating the session "
                    "(3) The bots expired "
                    "(the botworker stores bots for "
                    "only the most recent {} sessions).".format(
                        participant_code, SESSIONS_PRUNE_LIMIT)
                )
            }

        # so that any asserts in the PlayerBot work.
        bot.path = path
        bot.html = html

        with prepare_submit_lock:
            if participant_code in self.prepared_submits:
                return {}

            try:
                submission = next(bot.submits_generator)
            except StopIteration:
                # don't prune it because can cause flakiness if
                # there are other GET requests coming in. it will be pruned
                # when new sessions are created anyway.

                # need to return something, to distinguish from Redis timeout
                submission = {}
            else:
                # because we are returning it through Redis, need to pop it
                # here
                submission.pop('page_class')

            self.prepared_submits[participant_code] = submission

        return submission

    def ping(self, *args, **kwargs):
        return {'ok': True}

    def redis_listen(self):
        print('botworker is listening for messages through Redis')
        while True:
            self.process_one_message()

    def process_one_message(self):
        '''break it out into a separate method for testing purposes'''
        retval = None

        # blpop returns a tuple
        result = None

        # put it in a loop so that we can still receive KeyboardInterrupts
        # otherwise it will block
        while result is None:
            result = self.redis_conn.blpop(REDIS_KEY_PREFIX, timeout=3)

        key, message_bytes = result
        message = json.loads(message_bytes.decode('utf-8'))
        response_key = message['response_key']

        try:
            cmd = message['command']
            args = message.get('args', [])
            kwargs = message.get('kwargs', {})
            method = self.get_method(cmd)
            retval = method(*args, **kwargs)
        except Exception as exc:
            # request_error means the request received through Redis
            # was invalid.
            # response_error means the botworker raised while processing
            # the request.
            retval = {
                'response_error': repr(exc),
                'traceback': traceback.format_exc()
            }
            # don't raise, because then this would crash.
            # logger.exception() will record the full traceback
            logger.exception(repr(exc))
        finally:
            retval_json = json.dumps(retval or {})
            self.redis_conn.rpush(response_key, retval_json)


class BotWorkerPingError(Exception):
    pass


def ping(redis_conn, *, timeout):
    '''
    timeout arg is required because this is often called together
    with another function that has a timeout. need to be aware of double
    timeouts piling up.
    '''
    unique_response_code = otree.common_internal.random_chars_8()
    response_key = '{}-ping-{}'.format(REDIS_KEY_PREFIX, unique_response_code)
    msg = {
        'command': 'ping',
        'response_key': response_key,
    }
    redis_conn.rpush(REDIS_KEY_PREFIX, json.dumps(msg))
    # make it very long, so we don't get spurious ping errors
    result = redis_conn.blpop(response_key, timeout)

    if result is None:
        raise BotWorkerPingError(
            'Ping to botworker failed. '
            'If you want to use browser bots, '
            'you need to be running the botworker '
            '(which is started automatically if you run "otree runprodserver" '
            'or "otree timeoutworker"). '
            'Otherwise, set ("use_browser_bots": False) in the session config '
            'in settings.py.'
        )


def ping_bool(redis_conn, *, timeout):
    '''version of ping that returns True/False rather than raising'''
    try:
        ping(redis_conn, timeout=timeout)
        return True
    except BotWorkerPingError:
        return False


def load_redis_response_dict(response_bytes):
    response = json.loads(response_bytes.decode('utf-8'))
    # response_error only exists if using Redis.
    # if using runserver, there is no need for this because the
    # exception is raised in the same thread.
    if 'traceback' in response:
        # cram the other traceback in this traceback message.
        # note:
        raise Exception(response['traceback'])
    return response


def initialize_bots_redis(*, redis_conn, session_pk, case_number=None):
    response_key = '{}-initialize-{}'.format(REDIS_KEY_PREFIX, session_pk)
    msg = {
        'command': 'initialize_session',
        'kwargs': {'session_pk': session_pk, 'case_number': case_number},
        'response_key': response_key,
    }
    redis_conn.rpush(REDIS_KEY_PREFIX, json.dumps(msg))
    # ping will raise if it times out
    ping(redis_conn, timeout=4)

    # timeout must be int.
    # my tests show that it can initialize about 3000 players per second.
    # so 300-500 is conservative, plus pad for a few seconds
    #timeout = int(6 + num_players_total / 500)
    timeout = 6 # FIXME: adjust to number of players
    # maybe number of ParticipantToPlayerLookups?

    result = redis_conn.blpop(response_key, timeout=timeout)
    if result is None:
        raise Exception(
            'botworker is running but could not initialize the bot '
            'within {} seconds.'.format(timeout)
        )
    key, response_bytes = result
    load_redis_response_dict(response_bytes)
    return {'ok': True}


def initialize_bots_in_process(*, session_pk: int, case_number):
    browser_bot_worker.initialize_session(
        session_pk=session_pk, case_number=case_number)


def initialize_bots(*, session: Session, case_number):

    if otree.common_internal.USE_REDIS:
        initialize_bots_redis(
            redis_conn=get_redis_conn(),
            session_pk=session.pk,
            case_number=case_number,
        )
    else:
        initialize_bots_in_process(session_pk=session.pk, case_number=case_number)

def redis_flush_bots(redis_conn):
    for key in redis_conn.scan_iter(match='{}*'.format(REDIS_KEY_PREFIX)):
        redis_conn.delete(key)


class EphemeralBrowserBot(object):

    def __init__(self, view, redis_conn=None):
        self.view = view
        self.participant = view.participant
        self.session = self.view.session
        self.redis_conn = redis_conn or get_redis_conn()
        self.path = self.view.request.path

    def prepare_next_submit_redis(self, html):
        participant_code = self.participant.code
        response_key = '{}-prepare_next_submit-{}'.format(
            REDIS_KEY_PREFIX, participant_code)
        msg = {
            'command': 'prepare_next_submit',
            'kwargs': {
                'participant_code': participant_code,
                'path': self.path,
                'html': html,
            },
            'response_key': response_key,
        }
        return self.get_redis_response(msg)

    def get_redis_response(self, msg: dict):
        response_key = msg['response_key']
        redis_conn = self.redis_conn
        redis_conn.rpush(REDIS_KEY_PREFIX, json.dumps(msg))
        # in practice is very fast...around 1ms
        # however, if an exception occurs, could take quite long.
        # so, make this very long so we don't get spurious errors.
        # no advantage to cutting it off early.
        # if it's that slow consistently, people will complain.
        result = redis_conn.blpop(response_key, timeout=6)
        if result is None:
            # ping will raise if it times out
            ping(redis_conn, timeout=3)
            raise Exception(
                'botworker is running but did not return a submission.'
            )
        key, submit_bytes = result
        return load_redis_response_dict(submit_bytes)

    def prepare_next_submit_in_process(self, html):
        return browser_bot_worker.prepare_next_submit(
            self.participant.code, self.path, html)

    def prepare_next_submit(self, html):
        if otree.common_internal.USE_REDIS:
            result = self.prepare_next_submit_redis(html)
        else:
            result = self.prepare_next_submit_in_process(html)
        if 'request_error' in result:
            raise AssertionError(result['request_error'])

    def get_next_post_data_redis(self):
        participant_code = self.participant.code
        response_key = '{}-consume_next_submit-{}'.format(
            REDIS_KEY_PREFIX, participant_code)
        msg = {
            'command': 'consume_next_submit',
            'kwargs': {
                'participant_code': participant_code,
            },
            'response_key': response_key,
        }
        return self.get_redis_response(msg)

    def get_next_post_data(self):
        if otree.common_internal.USE_REDIS:
            submission = self.get_next_post_data_redis()
        else:
            submission = browser_bot_worker.prepared_submits.pop(
                self.participant.code)
        if submission:
            return submission['post_data']
        else:
            raise StopIteration('No more submits')

    def send_completion_message(self):
        channels.Group(
            'browser-bots-client-{}'.format(self.session.code)
        ).send({'text': self.participant.code})
