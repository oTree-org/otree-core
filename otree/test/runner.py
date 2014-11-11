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
import decimal
import random
import time
import logging
import Queue as queue

from django.utils.importlib import import_module

from django import test
from django.test import runner

from otree import constants, session
from otree.test import client

import coverage

import easymoney


#==============================================================================
# CONSTANTS
#==============================================================================

COVERAGE_MODELS = ['models', 'tests', 'views']


#==============================================================================
# LOGGER
#==============================================================================

logger = logging.getLogger(__name__)


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

    def _run_subsession(self, subsession):
        app_label = subsession._meta.app_label

        logger.info("Starting subsession '{}'".format(app_label))
        try:
            test_module_name = '{}.tests'.format(app_label)
            test_module = import_module(test_module_name)
            logger.info("Found test '{}'".format(test_module_name))
        except ImportError:
            self.fail("'{}' has no tests.py module".format(app_label))

        logger.info("Creating bots for '{}'".format(app_label))

        # ExperimenterBot is optional
        ExperimenterBotCls = getattr(
            test_module, 'ExperimenterBot', ExperimenterBot
        )
        experimenter_bot = ExperimenterBotCls(subsession)
#~
#~
        #~ failure_queue = queue.Queue()
#~
        #~ success = (failure_queue.qsize() == 0)
        #~ if success:
            #~ log.info("{}: tests completed successfully".format(app_label))
        #~ else:
            #~ log.info("{}: tests failed".format(app_label))
        #~ return success

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
            #~ if not
                #~ logger.info("Some tests in session '{}' failed".format(session_name))
    #~ return success


#==============================================================================
# RUNNER
#==============================================================================

class OTreeExperimentTestRunner(runner.DiscoverRunner):

    def build_suite(self, test_labels, extra_tests, **kwargs):

        directory = session.SessionTypeDirectory()
        available_sessions = directory.session_types_as_dict.keys()
        session_names = set()
        if test_labels:
            session_names.update(
                [name for name in test_labels if name in available_sessions]
            )
        else:
            session_names.update(available_sessions)

        tests = []
        for session_name in session_names:
            case = OTreeExperimentFunctionTest(session_name)
            tests.append(case)
        return super(OTreeExperimentTestRunner, self).build_suite(
            test_labels=(), extra_tests=tests, **kwargs
        )


#==============================================================================
# RUNNER
#==============================================================================

def run(session_names=None, with_coverage=True):

    directory = session.SessionTypeDirectory()
    if session_names is None:
        session_names = tuple(directory.session_types_as_dict.keys())

    #======================================
    # COVERAGE START
    #======================================

    cov = None
    if with_coverage:
        app_labels = set()
        for name, session_obj in directory.session_types_as_dict.items():
            if name in session_names:
                apps = directory.get_item(name).subsession_apps
                app_labels.update(apps)

        package_names = set()
        for app_label in app_labels:
            for module_name in COVERAGE_MODELS:
                module = '{}.{}'.format(app_label, module_name)
                package_names.add(module)

        cov = coverage.coverage(source=package_names)
        cov.start()

        for app_label in app_labels:
            models_module = '{}.models'.format(app_label)
            reload(sys.modules[models_module])

    #======================================
    # RUN TESTS
    #======================================

    status_results = {}
    for session_name in session_names:
        status = _run_session(session_name)
        status_results[session_name] = status

    #======================================
    # COVERAGE STOP
    #======================================

    if with_coverage:
        cov.stop()

    #======================================
    # END
    #======================================

    return status_results, cov
