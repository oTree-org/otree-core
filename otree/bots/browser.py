from __future__ import absolute_import
from .bot import ParticipantBot, Pause, submission_as_dict
import json
from otree.models import Session
from otree.common_internal import get_redis_conn, get_dotted_name
import otree.common_internal
import channels
import time
from collections import OrderedDict
from otree.session import SessionConfig
import random

REDIS_KEY = 'otree-bots'

SESSIONS_PRUNE_LIMIT = 50

# global variable that holds the browser bot worker instance in memory
browser_bot_worker = None # type: Worker


class Worker(object):
    def __init__(self, redis_conn=None):
        self.redis_conn = redis_conn
        self.browser_bots = {}
        self.session_participants = OrderedDict()

    def initialize_session(self, session_code):
        session = Session.objects.get(code=session_code)
        self.prune()
        self.session_participants[session_code] = []

        for participant in session.get_participants().filter(_is_bot=True):
            self.session_participants[session_code].append(
                participant.code)
            self.browser_bots[participant.code] = ParticipantBot(
                participant)
        return {'ok': True}

    def get_method(self, command_name):
        commands = {
            'get_next_submit': self.get_next_submit,
            'initialize_session': self.initialize_session,
            'clear_all': self.clear_all,
            'ping': self.ping,
        }

        return commands[command_name]

    def prune(self):
        '''to avoid memory leaks'''
        if len(self.session_participants) > SESSIONS_PRUNE_LIMIT:
            _, p_codes = self.session_participants.popitem(last=False)
            for participant_code in p_codes:
                self.browser_bots.pop(participant_code, None)

    def clear_all(self):
        self.browser_bots.clear()

    def get_next_submit(self, participant_code):
        try:
            bot = self.browser_bots[participant_code]
        except KeyError:
            return {
                'request_error': (
                    "Participant {} not loaded in botworker. "
                    "The botworker only stores the most recent {} sessions, "
                    "and discards older sessions. Or, maybe the botworker "
                    "was restarted after the session was created.".format(
                        participant_code, SESSIONS_PRUNE_LIMIT)
                )
            }
        try:
            while True:
                submit = next(bot.submits_generator)

                if isinstance(submit, Pause):
                    # pauses are ignored when running browser bots,
                    # because browser bots are for testing, not for real studies.
                    # real studies should use regular bots
                    continue
                else:
                    # not serializable
                    submission = submission_as_dict(submit)
                    submission.pop('page_class', None)
                    return submission
        except StopIteration:
            # clear it from memory
            self.browser_bots.pop(participant_code, None)
            # need to return something, to distinguish from timeout
            return {}

    def ping(self, *args, **kwargs):
        return {'ok': True}

    def redis_listen(self):
        print('botworker is listening for messages through Redis')
        while True:
            retval = None

            # blpop returns a tuple
            result = None

            # put it in a loop so that we can still receive KeyboardInterrupts
            # otherwise it will block
            while result == None:
                result = self.redis_conn.blpop(REDIS_KEY, timeout=3)

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
                # response_error means the botworker failed for an unknown
                # reason
                # request_error means the request received through Redis
                # was invalid
                retval = {'response_error': str(exc)}
                # execute finally below, then raise
                raise
            finally:
                retval_json = json.dumps(retval or {})
                self.redis_conn.rpush(response_key, retval_json)

def ping(redis_conn, unique_response_code):
    response_key = '{}-ping-{}'.format(REDIS_KEY, unique_response_code)
    msg = {
        'command': 'ping',
        'response_key': response_key,
    }
    redis_conn.rpush(REDIS_KEY, json.dumps(msg))
    result = redis_conn.blpop(response_key, timeout=1)

    if result is None:
        raise Exception(
            'Ping to botworker failed. '
            'If you want to use browser bots, '
            'you need to be running the botworker.'
            'Otherwise, set ("use_browser_bots": False) in the session config '
            'in settings.py.'
        )

def initialize_bots_redis(redis_conn, session_code, num_players_total):
    response_key = '{}-initialize-{}'.format(REDIS_KEY, session_code)
    msg = {
        'command': 'initialize_session',
        'kwargs': {'session_code': session_code},
        'response_key': response_key,
    }
    # ping will raise if it times out
    ping(redis_conn, session_code)
    redis_conn.rpush(REDIS_KEY, json.dumps(msg))

    # timeout must be int
    # this is about 10x as much time as it should take
    timeout = int(max(1, num_players_total * 0.1))
    result = redis_conn.blpop(response_key, timeout=timeout)
    if result is None:
        raise Exception(
            'botworker is running but could not initialize the session. '
            'within {} seconds.'.format(timeout)
        )
    key, submit_bytes = result
    value = json.loads(submit_bytes.decode('utf-8'))
    if 'response_error' in value:
        raise Exception(
            'An error occurred. See the botworker output for the traceback.')
    return {'ok': True}


def initialize_bots_in_process(session_code):
    browser_bot_worker.initialize_session(session_code)

def initialize_bots(session_code, num_players_total):
    if otree.common_internal.USE_REDIS:
        initialize_bots_redis(
            redis_conn=get_redis_conn(),
            session_code=session_code,
            num_players_total=num_players_total
        )
    else:
        initialize_bots_in_process(session_code)

def redis_flush_bots(redis_conn):
    for key in redis_conn.scan_iter(match='{}*'.format(REDIS_KEY)):
        redis_conn.delete(key)


class EphemeralBrowserBot(object):

    def __init__(self, view, redis_conn=None):
        self.view = view
        self.participant = view.participant
        self.session = self.view.session
        self.redis_conn = redis_conn or get_redis_conn()

    def get_submit_redis(self):
        participant_code = self.participant.code
        redis_conn = self.redis_conn
        response_key = '{}-get_next_submit-{}'.format(
            REDIS_KEY, participant_code)
        msg = {
            'command': 'get_next_submit',
            'kwargs': {'participant_code': participant_code},
            'response_key': response_key,
        }
        redis_conn.rpush(REDIS_KEY, json.dumps(msg))
        # in practice is very fast...around 1ms
        result = redis_conn.blpop(response_key, timeout=1)
        if result is None:
            # ping will raise if it times out
            ping(redis_conn, participant_code)
            raise Exception(
                'botworker is running but did not return a submission.'
            )
        key, submit_bytes = result
        submission = json.loads(submit_bytes.decode('utf-8'))
        if 'response_error' in submission:
            raise Exception(
                'An error occurred. See the botworker output '
                'for the traceback.')
        return submission

    def get_submit_in_process(self):
        return browser_bot_worker.get_next_submit(self.participant.code)

    def get_next_post_data(self):
        if otree.common_internal.USE_REDIS:
            submission = self.get_submit_redis()
        else:
            submission = self.get_submit_in_process()
        if 'request_error' in submission:
            raise Exception(submission['request_error'])
        if submission:
            page_class_dotted = submission['page_class_dotted']
            this_page_dotted = get_dotted_name(self.view.__class__)

            if not page_class_dotted == this_page_dotted:
                raise ValueError(
                    "Bot is trying to submit page {}, "
                    "but current page is {}. "
                    "Check your bot in tests.py, "
                    "then create a new session.".format(
                        page_class_dotted,
                        this_page_dotted
                    )
                )

            return submission['post_data']
        else:
            raise StopIteration

    def send_completion_message(self):
        channels.Group(
            'browser-bots-client-{}'.format(self.session.code)
        ).send({'text': self.participant.code})
