#!/usr/bin/env python
# -*- coding: utf-8 -*-

#==============================================================================
# DOCS
#==============================================================================

"""Basic structures and functionality for running tests on otree

"""

#==============================================================================
# IMPORTS
#==============================================================================

import sys
import logging
import contextlib
import collections
import itertools
import time
import random

from django.utils.importlib import import_module

from django import test
from django.test import runner

from otree import constants, session
from otree.test import client

import coverage

#==============================================================================
# CONSTANTS
#==============================================================================

COVERAGE_MODELS = ['models', 'tests', 'views']

MAX_ATTEMPTS = 100


#==============================================================================
# LOGGER
#==============================================================================

logger = logging.getLogger(__name__)


#==============================================================================
# DUMMY EXPERIMENTER BOT
#==============================================================================

class DummyExperimenterBot(client.BaseExperimenterBot):

    def play(self):
        pass

    def validate_play(self):
        pass


#==============================================================================
# TEST CASE
#==============================================================================

class OTreeExperimentFunctionTest(test.TransactionTestCase):

    def __init__(self, session_name):
        super(OTreeExperimentFunctionTest, self).__init__()
        self.session_name = session_name

    def __repr__(self):
        return "<{} '{}'>".format(
            type(self).__name__, self.session_name, hex(id(self))
        )

    def __str__(self):
        return "ExperimentTest For '{}'".format(self.session_name)

    def zip_submits(self, bots):
        bots = list(bots)
        random.shuffle(bots)
        submits = map(lambda b: b.submits, bots)
        return list(itertools.izip_longest(*submits))

    def _run_subsession(self, subsession):
        app_label = subsession.app_name

        logger.info("Starting subsession '{}'".format(app_label))
        try:
            test_module_name = '{}.tests'.format(app_label)
            test_module = import_module(test_module_name)
            logger.info("Found test '{}'".format(test_module_name))
        except ImportError:
            self.fail("'{}' has no tests.py module".format(app_label))

        logger.info("Creating and staring bots for '{}'".format(app_label))

        # ExperimenterBot is optional
        ExperimenterBotCls = getattr(
            test_module, 'ExperimenterBot', DummyExperimenterBot
        )

        # create the bots
        bots = []

        ex_bot = ExperimenterBotCls(subsession)
        ex_bot.start()
        bots.append(ex_bot)

        for player in subsession.player_set.all():
            bot = test_module.PlayerBot(player)
            bot.start()
            bots.append(bot)

        submit_groups = self.zip_submits(bots)
        pending = collections.OrderedDict()
        while pending or submit_groups:
            for submit, attempts in tuple(pending.items()):
                if attempts > MAX_ATTEMPTS:
                    msg = "Max attepts reached in  submit '{}'"
                    raise AssertionError(msg.format(submit))
                if submit.execute():
                    pending.pop(submit)
                else:
                    pending[submit] += 1

            # ejecutar un grupo
            group = submit_groups.pop(0) if submit_groups else ()
            for submit in group:
                if submit is None:
                    continue
                if not submit.execute():
                    pending[submit] = 1

        logger.info("Stoping bots for '{}'".format(app_label))
        for bot in bots:
            bot.stop()

    def runTest(self):
        logger.info("Creating session for experimenter on session '{}'".format(
            self.session_name
        ))
        sssn = session.create_session(
            type_name=self.session_name,
            special_category=constants.special_category_bots
        )
        sssn.label = '{} [bots]'.format(self.session_name)
        sssn.save()

        msg = "Creating session experimenter on session '{}'"
        logger.info(msg.format(self.session_name))

        sssn_exbot = test.Client()
        sssn_exbot.get(sssn.session_experimenter._start_url(), follow=True)
        sssn_exbot.post(sssn.session_experimenter._start_url(), follow=True)

        #~ # since players are assigned to groups in a background thread,
        #~ # we need to wait for that to complete.
        logger.info("Adding bots on session '{}'".format(self.session_name))
        while True:
            sssn = session.models.Session.objects.get(id=sssn.pk)
            if sssn._players_assigned_to_groups:
                break
            time.sleep(1)

        msg = "'GET' over first page of all '{}' participants"
        logger.info(msg.format(self.session_name))

        for participant in sssn.get_participants():
            bot = test.Client()
            bot.get(participant._start_url(), follow=True)

        logger.info("Running subsessions of '{}'".format(self.session_name))

        for subsession in sssn.get_subsessions():
            self._run_subsession(subsession)


#==============================================================================
# RUNNER
#==============================================================================

class OTreeExperimentTestRunner(runner.DiscoverRunner):

    def build_suite(self, session_names, extra_tests, **kwargs):

        if not session_names:
            directory = session.SessionTypeDirectory()
            session_names = directory.session_types_as_dict.keys()

        tests = []
        for session_name in session_names:
            case = OTreeExperimentFunctionTest(session_name)
            tests.append(case)
        return super(OTreeExperimentTestRunner, self).build_suite(
            test_labels=(), extra_tests=tests, **kwargs
        )


#==============================================================================
# HELPER
#==============================================================================

def apps_from_sessions(session_names=None):
    directory = session.SessionTypeDirectory()
    if session_names:
        session_names = frozenset(session_names)
    else:
        session_names = frozenset(directory.session_types_as_dict.keys())
    apps = set()
    for sname in session_names:
        sssn = directory.get_item(sname)
        apps.update(sssn.subsession_apps)
    return apps


#==============================================================================
# COVERAGE CONTEXT
#==============================================================================

@contextlib.contextmanager
def covering(session_names=None):
    package_names = set()
    for app_label in apps_from_sessions(session_names):
        for module_name in COVERAGE_MODELS:
            module = '{}.{}'.format(app_label, module_name)
            package_names.add(module)

    cov = coverage.coverage(source=package_names)

    cov.start()
    try:
        yield cov
    finally:
        cov.stop()
