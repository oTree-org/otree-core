#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# DOCS
# =============================================================================

"""Basic structures and functionality for running tests on otree

"""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
import contextlib
from collections import OrderedDict
import mock
from huey.contrib.djhuey import task, db_task
import json
import random
import channels
from six import StringIO
from django.db.migrations.loader import MigrationLoader
from django import test
from django.test import runner
from unittest import TestSuite

from otree import common_internal
import otree.session
from otree.models import Session
from .bot import ParticipantBot, Pause


MAX_ATTEMPTS = 100


logger = logging.getLogger(__name__)


# global variable, store bot runners in memory
session_bot_runners = {}


class SessionBotRunner(object):
    def __init__(self, bots, session_code):
        self.session_code = session_code
        self.stuck = OrderedDict()
        self.playable = OrderedDict()
        self.all_bot_ids = {bot.participant.id for bot in bots}

        for bot in bots:
            self.playable[bot.participant.id] = bot

    def play_until_end(self):
        while True:
            # keep un-sticking everyone who's stuck
            stuck_pks = list(self.stuck.keys())
            done, num_submits_made = self.play_until_stuck(stuck_pks)
            if done:
                print('Bots done!')
                return
            #elif num_submits_made == 0:
            #    print('Bots got stuck :(')
            #    break

    def play_until_stuck(self, unstuck_ids=None):
        unstuck_ids = unstuck_ids or []
        for pk in unstuck_ids:
            # the unstuck ID might be a human player, not a bot.
            if pk in self.all_bot_ids:
                self.playable[pk] = self.stuck.pop(pk)
        num_submits_made = 0
        while True:
            # round-robin algorithm
            if len(self.playable) == 0:
                if len(self.stuck) == 0:
                    # finished! send a message somewhere?
                    # clear from the global var
                    session_bot_runners.pop(self.session_code, None)
                    return (True, num_submits_made)
                # stuck
                return (False, num_submits_made)
            # store in a separate list so we don't mutate the iterable
            playable_ids = list(self.playable.keys())
            for pk in playable_ids:
                bot = self.playable[pk]
                if bot.on_wait_page():
                    self.stuck[pk] = self.playable.pop(pk)
                else:
                    try:
                        value = next(bot.submits_generator)
                    except StopIteration:
                        # this bot is finished
                        self.playable.pop(pk)
                    else:
                        if isinstance(value, Pause):
                            # can only schedule it if we're using redis.
                            # otherwise, ignore
                            if common_internal.USE_REDIS:
                                # submit is actually a pause
                                pause = value
                                self.stuck[pk] = self.playable.pop(pk)
                                continue_bots_until_stuck_task.schedule(
                                    [self.session_code, [pk]],
                                    delay=pause.seconds
                                )
                        else:
                            submission = value
                            bot.submit(submission)
                            num_submits_made += 1


def start_bots(session):

    if session._cannot_restart_bots:
        return
    session._cannot_restart_bots = True
    session.save()

    bots = []

    has_human_participants = session.get_participants().filter(
        _is_bot=False).exists()
    if has_human_participants:
        max_wait_seconds = None
    else:
        max_wait_seconds = 10

    for participant in session.get_participants().filter(_is_bot=True):
        bot = ParticipantBot(participant, max_wait_seconds=max_wait_seconds)
        bots.append(bot)
        bot.open_start_url()

    bot_runner = SessionBotRunner(bots, session.code)
    session_bot_runners[session.code] = bot_runner


@db_task()
def play_bots_task(session_code):
    '''when doing this through Huey'''
    session = Session.objects.get(code=session_code)
    start_bots(session)
    bot_runner = session_bot_runners[session.code]
    bot_runner.play_until_stuck()


@db_task()
def continue_bots_until_stuck_task(session_code, unstuck_ids=None):
    channels_group = channels.Group('session-admin-{}'.format(session_code))
    try:
        bot_runner = session_bot_runners[session_code]
    except KeyError:
        logger.warning('Bot finished, nothing to continue')
        return
    try:
        bot_runner.play_until_stuck(unstuck_ids)
    except Exception as exc:
        session = Session.objects.get(code=session_code)
        session._bots_errored = True
        session.save()
        error_msg = (
            'Bots encountered an error: "{}". For the full traceback, '
            'see the server logs.'.format(exc))
        channels_group.send({'text': json.dumps({'message': error_msg})})
        raise
    channels_group.send(
            {'text': json.dumps(
                {'message': 'Bots finished'})})
    session = Session.objects.get(code=session_code)
    session._bots_finished = True
    session.save()


class BotsTestCase(test.TransactionTestCase):

    def __init__(self, config_name, preserve_data):
        super(BotsTestCase, self).__init__()
        self.config_name = config_name
        self.preserve_data = preserve_data
        self._data_for_export = None

    def __repr__(self):
        hid = hex(id(self))
        return "<{} '{}'>".format(type(self).__name__, self.config_name, hid)

    def __str__(self):
        return "Bots for session '{}'".format(self.config_name)

    def tearDown(self):
        if self.preserve_data:
            logger.info(
                "Collecting data for session '{}'".format(self.config_name))
            buff = StringIO()
            common_internal.export_data(buff, self.config_name)
            self._data_for_export = buff.getvalue()

    def get_export_data(self):
        return self._data_for_export

    def create_session(self):
        logger.info("Creating '{}' session".format(self.config_name))

        return otree.session.create_session(
            session_config_name=self.config_name,
            use_cli_bots=True, label='{} [bots]'.format(self.config_name)
        )

    def runTest(self):

        session = self.create_session()
        start_bots(session)
        bot_runner = session_bot_runners[session.code]
        bot_runner.play_until_end()


# =============================================================================
# RUNNER
# =============================================================================

class BotsTestSuite(TestSuite):
    def _removeTestAtIndex(self, index):
        # In Python 3.4 and above, is the TestSuite clearing all references to
        # the test cases after the suite has finished. That way, the
        # ``OTreeExperimentTestRunner.suite_result`` cannot retrieve the data
        # in order to prepare it for CSV test data export.

        # We overwrite this function in order to keep the testcase instances
        # around.
        pass


class BotsDiscoverRunner(runner.DiscoverRunner):
    test_suite = BotsTestSuite

    def build_suite(self, config_names, extra_tests, preserve_data, **kwargs):
        suite = self.test_suite()
        for config_name in config_names:
            case = BotsTestCase(config_name, preserve_data)
            suite.addTest(case)
        return suite

    def suite_result(self, suite, result, *args, **kwargs):
        failures = super(BotsDiscoverRunner, self).suite_result(
            suite, result, *args, **kwargs)
        data = {case.config_name: case.get_export_data() for case in suite}
        return failures, data

    def run_tests(self, test_labels, extra_tests=None,
                  preserve_data=False, **kwargs):
        self.setup_test_environment()
        suite = self.build_suite(test_labels, extra_tests, preserve_data)
        # same hack as in resetdb code
        # because this method uses the serializer
        # it breaks if the app has migrations but they aren't up to date
        with mock.patch.object(
                MigrationLoader,
                'migrations_module',
                return_value='migrations nonexistent hack'
        ):
            old_config = self.setup_databases()
        result = self.run_suite(suite)
        failures, data = self.suite_result(suite, result)
        self.teardown_databases(old_config)
        self.teardown_test_environment()
        return failures, data
