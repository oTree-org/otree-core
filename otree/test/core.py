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
import logging
import Queue as queue

from django.utils.importlib import import_module
from django import test

from otree import constants, session

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
# CLASS
#==============================================================================

class PlayerBot(test.Client):

    pass



#==============================================================================
# RUNNER
#==============================================================================

def _run_session(session_name):
    logger.info (
        "Creating session for experimenter on session '{}'".format(
            session_name
        )
    )
    sssn = session.create_session(
        type_name=session_name,
        special_category=constants.special_category_bots
    )
    sssn.label = '{} [bots]'.format(session_name)
    sssn.save()

    logger.info(
        "Creating session experimenter on session '{}'".format(session_name)
    )
    sssn_exbot = test.Client()
    sssn_exbot.get(sssn.session_experimenter._start_url(), follow=True)
    rp = sssn_exbot.post(sssn.session_experimenter._start_url(), follow=True)

    # since players are assigned to groups in a background thread,
    # we need to wait for that to complete.
    logger.info ("Adding bots on session '{}'".format(session_name))
    while True:
        sssn = session.models.Session.objects.get(id=sssn.pk)
        if sssn._players_assigned_to_groups:
            break
        time.sleep(1)

    import ipdb; ipdb.set_trace()


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
