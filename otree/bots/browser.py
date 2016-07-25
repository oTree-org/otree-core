from .bot import ParticipantBot, Pause, submission_as_dict
import json
from otree.models import Session
from otree.common_internal import get_redis_conn

REDIS_KEY = 'otree-bots'

ERROR_NO_BOT_FOR_PARTICIPANT = 'ERROR_NO_BOT_FOR_PARTICIPANT'


class Consumer(object):
    def __init__(self, redis_conn):
        self.redis_conn = redis_conn
        self.browser_bots = {}

    def initialize_session(self, session_code):
        session = Session.objects.get(code=session_code)
        for participant in session.get_participants().filter(_is_bot=True):
            self.browser_bots[participant.code] = ParticipantBot(participant)
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
    result = redis_conn.blpop(response_key, timeout=2)
    if result is None:
        raise Exception(
            'Ping to botworker failed. '
            'To use browser bots, you need to be running the botworker.'
        )
    return {'ok': True}


def get_next_submit(redis_conn, participant_code):
    response_key = '{}-get_next_submit-{}'.format(REDIS_KEY, participant_code)
    msg = {
        'command': 'get_next_submit',
        'kwargs': {'participant_code': participant_code},
        'response_key': response_key,
    }
    redis_conn.rpush(REDIS_KEY, json.dumps(msg))
    result = redis_conn.blpop(response_key, timeout=3)
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
            'An error occurred. See the botworker output for the traceback.')
    return submission


def initialize_bots(redis_conn, session_code):
    response_key = '{}-initialize-{}'.format(REDIS_KEY, session_code)
    msg = {
        'command': 'initialize_session',
        'kwargs': {'session_code': session_code},
        'response_key': response_key,
    }
    redis_conn.rpush(REDIS_KEY, json.dumps(msg))
    result = redis_conn.blpop(response_key, timeout=5)
    print('result from initialize_bots:', result)
    if result is None:
        # ping will raise if it times out
        ping(redis_conn, session_code)
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
