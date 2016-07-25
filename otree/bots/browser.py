from __future__ import absolute_import
from .bot import ParticipantBot, Pause, submission_as_dict
import json
from otree.models import Session
from otree.common_internal import get_redis_conn, get_dotted_name
import channels
import time

REDIS_KEY = 'otree-bots'

ERROR_NO_BOT_FOR_PARTICIPANT = 'ERROR_NO_BOT_FOR_PARTICIPANT'


class Worker(object):
    def __init__(self, redis_conn):
        self.redis_conn = redis_conn
        self.browser_bots = {}

    def initialize_session(self, session_code):
        session = Session.objects.get(code=session_code)
        for participant in session.get_participants().filter(_is_bot=True):
            self.browser_bots[participant.code] = ParticipantBot(participant)
        print('{} items in browser bot dict'.format(len(self.browser_bots)))
        return {'ok': True}

    def get_method(self, command_name):
        commands = {
            'get_next_submit': self.get_next_submit,
            'initialize_session': self.initialize_session,
            'clear_all': self.clear_all,
            'ping': self.ping,
        }

        return commands[command_name]


    def clear_all(self):
        self.browser_bots.clear()

    def get_next_submit(self, participant_code):
        try:
            bot = self.browser_bots[participant_code]
        except KeyError:
            raise KeyError(
                "Participant {} not loaded in botworker. "
                "Maybe botworker was restarted "
                "after the session was created.".format(participant_code)
            )
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

    def loop(self):
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
                retval = {'error': str(exc)}
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
    start = time.time()
    result = redis_conn.blpop(response_key, timeout=3)
    print('{}s to ping botworker'.format(time.time() - start))

    if result is None:
        raise Exception(
            'Ping to botworker failed. '
            'To use browser bots, you need to be running the botworker.'
        )



def initialize_bots(redis_conn, session_code):
    response_key = '{}-initialize-{}'.format(REDIS_KEY, session_code)
    msg = {
        'command': 'initialize_session',
        'kwargs': {'session_code': session_code},
        'response_key': response_key,
    }
    # ping will raise if it times out
    ping(redis_conn, session_code)
    redis_conn.rpush(REDIS_KEY, json.dumps(msg))
    start = time.time()
    result = redis_conn.blpop(response_key, timeout=60)
    print('{}s to initialize bots in botworker'.format(time.time() - start))
    if result is None:
        raise Exception(
            'botworker is running but could not initialize the session.'
        )
    key, submit_bytes = result
    value = json.loads(submit_bytes.decode('utf-8'))
    if 'error' in value:
        raise Exception(
            'An error occurred. See the botworker output for the traceback.')
    return {'ok': True}


def redis_flush_bots(redis_conn):
    for key in redis_conn.scan_iter(match='{}*'.format(REDIS_KEY)):
        redis_conn.delete(key)


class BrowserBot(object):

    def __init__(self, view, redis_conn=None):
        self.view = view
        self.participant = view.participant
        self.session = self.view.session
        self.redis_conn = redis_conn or get_redis_conn()

    def get_next_submit(self):
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
        start = time.time()
        result = redis_conn.blpop(response_key, timeout=3)
        print('{}s to receive submit from botworker'.format(time.time() - start))
        if result is None:
            # ping will raise if it times out
            ping(redis_conn, participant_code)
            raise Exception(
                'botworker is running but did not return a submission.'
            )
        key, submit_bytes = result
        submission = json.loads(submit_bytes.decode('utf-8'))
        if 'error' in submission:
            raise Exception(
                'An error occurred. See the botworker output '
                'for the traceback.')
        page_class_dotted = submission['page_class_dotted']
        if submission:
            this_page_dotted = get_dotted_name(self.view.__class__)

            if not submission['page_class_dotted'] == this_page_dotted:
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
