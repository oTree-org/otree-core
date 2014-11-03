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

import decimal
import random

from django.utils.importlib import import_module
from django.test import client

import otree.constants
from otree.session import create_session, SessionTypeDirectory

import coverage

import easymoney


#==============================================================================
# CONSTANTS
#==============================================================================

COVERAGE_MODELS = ['models', 'tests', 'views']


#==============================================================================
# CLASS
#==============================================================================

class PlayerBot(client.Client):

    pass



#==============================================================================
# RUNNER
#==============================================================================

def _run_session(session_name):



def run(session_names=None, with_coverage=True):

    directory = SessionTypeDirectory()
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

    return status_results, cov
