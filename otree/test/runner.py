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
import itertools
import time
import random

from django.utils.importlib import import_module

from django import test
from django.test import runner
from django.template import response

import otree.models
from otree import constants, session

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


# =============================================================================
#
# =============================================================================

class MissingVarsContextProxyBase(object):
    """
    This is a poor-man's proxy for a context instance.

    Make sure template rendering stops immediately on a KeyError.

    bassed on: https://excess.org/article/2012/04/paranoid-django-templates/

    """
    CONTEXT_CLS = None

    def __init__(self, *args, **kwargs):
        self.context = self.CONTEXT_CLS(*args, **kwargs)
        self.seen_keys = set()

    def __repr__(self):
        return "<MV ({}) at {}>".format(type(self.CONTEXT_CLS))

    def __getitem__(self, key):
        self.seen_keys.add(key)
        try:
            return self.context[key]
        except KeyError:
            raise AssertionError("Missing template var '{}'".format(key))

    def __getattr__(self, name):
        return getattr(self.context, name)

    def __setitem__(self, key, value):
        self.context[key] = value

    def __delitem__(self, key):
        del self.context[key]


# =============================================================================
# PENDING LIST
# =============================================================================

class PendingBuffer(object):

    def __init__(self, app_label):
        self.storage = collections.OrderedDict()
        self.app_label = app_label

    def __str__(self):
        return repr(self)

    def __len__(self):
        return len(self.storage)

    def __nonzero__(self):
        return bool(self.storage)

    def __iter__(self):
        for k, v in self.storage.items():
            yield k, v
            if k in self.storage:
                self.storage[k] += 1

    def add(self, submit):
        if submit in self.storage:
            raise ValueError("Submit already in pending list")
        self.storage[submit] = 1

    def remove(self, submit):
        del self.storage[submit]

    def is_blocked(self, submit):
        return submit.bot in [s.bot for s in self.storage.keys()]


# =============================================================================
# TEST CASE
# =============================================================================

class OTreeExperimentFunctionTest(test.TransactionTestCase):

    def __init__(self, session_name):
        super(OTreeExperimentFunctionTest, self).__init__()
        self.session_name = session_name
        self.app_tested = []

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
        app_label = subsession._meta.app_config.name

        # patching round number
        self.app_tested.append(app_label)
        subsession.round_number = self.app_tested.count(app_label)

        logger.info("Starting subsession '{}'".format(app_label))
        try:
            test_module_name = '{}.tests'.format(app_label)
            test_module = import_module(test_module_name)
            logger.info("Found test '{}'".format(test_module_name))
        except ImportError as err:
            self.fail(unicode(err))

        logger.info("Creating and staring bots for '{}'".format(app_label))

        # create the bots
        bots = []

        for player in subsession.player_set.all():
            bot = test_module.PlayerBot(player)
            bot.start()
            bots.append(bot)

        submit_groups = self.zip_submits(bots)
        pending = PendingBuffer(app_label)
        while pending or submit_groups:
            for submit, attempts in pending:
                if attempts > MAX_ATTEMPTS:
                    msg = "Max attepts reached in  submit '{}'"
                    raise AssertionError(msg.format(submit))
                if submit.execute():
                    pending.remove(submit)

            group = submit_groups.pop(0) if submit_groups else ()
            for submit in group:
                if submit is None:
                    continue
                if pending.is_blocked(submit) or not submit.execute():
                    pending.add(submit)

        logger.info("Stopping bots for '{}'".format(app_label))
        for bot in bots:
            bot.stop()

    def runTest(self):
        logger.info("Creating session for experimenter on session '{}'".format(
            self.session_name
        ))
        sssn = session.create_session(
            session_type_name=self.session_name,
            special_category=constants.session_special_category_bots,
        )
        sssn.label = '{} [bots]'.format(self.session_name)
        sssn.save()

        # since players are assigned to groups in a background thread,
        # we need to wait for that to complete.
        logger.info("Adding bots on session '{}'".format(self.session_name))

        while True:
            sssn = otree.models.Session.objects.get(id=sssn.pk)
            if sssn._ready_to_play:
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


# =============================================================================
# RUNNER
# =============================================================================

class OTreeExperimentTestRunner(runner.DiscoverRunner):

    def build_suite(self, session_names, extra_tests, **kwargs):

        if not session_names:
            session_names = session.get_session_types_dict().keys()

        tests = []
        for session_name in session_names:
            case = OTreeExperimentFunctionTest(session_name)
            tests.append(case)
        return super(OTreeExperimentTestRunner, self).build_suite(
            test_labels=(), extra_tests=tests, **kwargs
        )

    def patch_validate_missing_template_vars(self):
        # black magic envolved
        ContextProxy = type(
            "ContextProxy", (MissingVarsContextProxyBase,),
            {"CONTEXT_CLS": response.Context}
        )
        setattr(response, "Context", ContextProxy)

        RequestContextProxy = type(
            "ContextProxy", (MissingVarsContextProxyBase,),
            {"CONTEXT_CLS": response.RequestContext}
        )
        setattr(response, "RequestContext", RequestContextProxy)


# =============================================================================
# HELPER
# =============================================================================

def apps_from_sessions(session_names=None):
    if session_names:
        session_names = frozenset(session_names)
    else:
        session_names = frozenset(session.get_session_types_dict().keys())
    apps = set()
    for sname in session_names:
        sssn = session.get_session_types_dict()[sname]
        apps.update(sssn.app_sequence)
    return apps


# =============================================================================
# COVERAGE CONTEXT
# =============================================================================

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
