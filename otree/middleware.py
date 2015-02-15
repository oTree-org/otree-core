#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTS
# =============================================================================

import sys

import six

from django.db import utils


# =============================================================================
# MIDDLEWARES
# =============================================================================

class OperationalErrorMidleware(object):

    def process_exception(self, request, exception):
        if isinstance(exception, utils.OperationalError):
            new_err = utils.OperationalError(
                "{} - Try resetting the database.".format(exception.message)
            )
            six.reraise(utils.OperationalError, new_err, sys.exc_traceback)
