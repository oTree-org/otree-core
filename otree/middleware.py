#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTS
# =============================================================================

from otree import common_internal


# =============================================================================
# MIDDLEWARES
# =============================================================================

class OperationalErrorMidleware(object):

    def process_exception(self, request, exception):
        common_internal.reraise(exception)
