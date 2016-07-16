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
import collections
from collections import deque
import mock
from huey.contrib.djhuey import task, db_task
import json

import channels
from six import StringIO
from django.db.migrations.loader import MigrationLoader
from django import test
from django.test import runner
from unittest import TestSuite

from otree import common_internal
import otree.session
from otree.models import Session
from .bot import ParticipantBot

import coverage

# =============================================================================
# CONSTANTS
# =============================================================================

COVERAGE_MODELS = ['models', 'tests', 'views']

MAX_ATTEMPTS = 100


# =============================================================================
# LOGGER
# =============================================================================

logger = logging.getLogger(__name__)


def play_bots(session_code):
    '''pass in session code rather than session object because it needs
    to be serialized to redis'''

    session = Session.objects.get(code=session_code)

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

    # TODO: handle max attempts or timeouts
    '''
    for submit, attempts in pending:
        if attempts > MAX_ATTEMPTS:
            msg = "Max attepts reached in  submit '{}'"
            raise AssertionError(msg.format(submit))
    '''

    # something like this...
    loop = async.get_loop()
    tasks = [bot.play_session() for bot in bots]
    loop.run_all(tasks)


@db_task()
def play_bots_task(session_code):
    channels_group = channels.Group('session-admin-{}'.format(session_code))
    session = Session.objects.get(code=session_code)
    try:
        play_bots(session)
    except Exception as exc:
        session._bots_errored = True
        session.save()
        error_msg = (
            'Bots encountered an error: "{}". For the full traceback, '
            'see the server logs.'.format(exc))
        channels_group.send({'text': json.dumps({'error': error_msg})})
        raise
    channels_group.send(
            {'text': json.dumps(
                {'message': 'Bots finished'})})
    session._bots_finished = True
    session.save()


class OTreeExperimentFunctionTest(test.TransactionTestCase):

    def __init__(self, session_name, preserve_data):
        super(OTreeExperimentFunctionTest, self).__init__()
        self.config_name = session_name
        self.preserve_data = preserve_data
        self._data_for_export = None

    def __repr__(self):
        hid = hex(id(self))
        return "<{} '{}'>".format(type(self).__name__, self.config_name, hid)

    def __str__(self):
        return "ExperimentTest for session '{}'".format(self.config_name)

    def tearDown(self):
        if self.preserve_data:
            logger.info(
                "Recolecting data for session '{}'".format(self.config_name))
            buff = StringIO()
            common_internal.export_data(buff, self.config_name)
            self._data_for_export = buff.getvalue()

    def get_export_data(self):
        return self._data_for_export

    def create_session(self):
        logger.info("Creating '{}' session".format(self.config_name))

        return otree.session.create_session(
            session_config_name=self.config_name,
            is_bots=True, label='{} [bots]'.format(self.config_name)
        )

    def runTest(self):

        session = self.create_session()
        play_bots(session)



# =============================================================================
# RUNNER
# =============================================================================

class OTreeExperimentTestSuite(TestSuite):
    def _removeTestAtIndex(self, index):
        # In Python 3.4 and above, is the TestSuite clearing all references to
        # the test cases after the suite has finished. That way, the
        # ``OTreeExperimentTestRunner.suite_result`` cannot retrieve the data
        # in order to prepare it for CSV test data export.

        # We overwrite this function in order to keep the testcase instances
        # around.
        pass


class OTreeExperimentTestRunner(runner.DiscoverRunner):
    test_suite = OTreeExperimentTestSuite

    def build_suite(self, session_names, extra_tests, preserve_data, **kwargs):
        suite = self.test_suite()
        for session_name in session_names:
            case = OTreeExperimentFunctionTest(session_name, preserve_data)
            suite.addTest(case)
        return suite

    def suite_result(self, suite, result, *args, **kwargs):
        failures = super(OTreeExperimentTestRunner, self).suite_result(
            suite, result, *args, **kwargs)
        data = {case.session_name: case.get_export_data() for case in suite}
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


# =============================================================================
# COVERAGE CONTEXT
# =============================================================================

@contextlib.contextmanager
def covering(session_names=None):
    package_names = set()
    for app_label in session.app_labels_from_sessions(session_names):
        for module_name in COVERAGE_MODELS:
            module = '{}.{}'.format(app_label, module_name)
            package_names.add(module)

    cov = coverage.coverage(source=package_names)
    cov.start()
    try:
        yield cov
    finally:
        cov.stop()
