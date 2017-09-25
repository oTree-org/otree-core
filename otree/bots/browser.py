#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import json
import threading
import logging
from collections import OrderedDict

from django.test import SimpleTestCase

import channels
import traceback

import otree.common_internal
from otree.models.participant import Participant
from otree.common_internal import get_redis_conn

from .bot import ParticipantBot


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

    def initialize_participant(self, participant_code):
        '''
        initialize participants one-by-one because when i did it all at once,
        i was getting some sort of timeout error
        See 4206a91e7d883983c59c240f61a342d93a582c93
        '''
        self.prune()

        participant = Participant.objects.select_related('session').get(
            code=participant_code)
        session_code = participant.session.code

        self.browser_bots[participant.code] = ParticipantBot(participant)

        with add_or_remove_bot_lock:
            if session_code not in self.participants_by_session:
                self.participants_by_session[session_code] = []
            self.participants_by_session[session_code].append(participant_code)

        return {'ok': True}

    def get_method(self, command_name):
        commands = {
            'prepare_next_submit': self.prepare_next_submit,
            'consume_next_submit': self.consume_next_submit,
            'initialize_participant': self.initialize_participant,
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


def initialize_bot_redis(redis_conn, participant_code):
    response_key = '{}-initialize-{}'.format(REDIS_KEY_PREFIX, participant_code)
    msg = {
        'command': 'initialize_participant',
        'kwargs': {'participant_code': participant_code},
        'response_key': response_key,
    }
    redis_conn.rpush(REDIS_KEY_PREFIX, json.dumps(msg))

    # timeout must be int
    # in my testing it takes 0.1 seconds usually.
    # but some users were still getting timeout errors with timeout=2
    timeout = 5
    result = redis_conn.blpop(response_key, timeout=timeout)
    if result is None:
        # ping will raise if it times out
        ping(redis_conn, timeout=5)
        raise Exception(
            'botworker is running but could not initialize the bot '
            'within {} seconds.'.format(timeout)
        )
    key, response_bytes = result
    load_redis_response_dict(response_bytes)
    return {'ok': True}


def initialize_bot_in_process(participant_code):
    browser_bot_worker.initialize_participant(participant_code)


def initialize_bot(participant_code):
    if otree.common_internal.USE_REDIS:
        initialize_bot_redis(
            redis_conn=get_redis_conn(),
            participant_code=participant_code,
        )
    else:
        initialize_bot_in_process(participant_code)


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
        redis_conn = self.redis_conn
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
