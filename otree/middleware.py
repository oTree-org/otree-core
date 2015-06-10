#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTS
# =============================================================================

from django.http import HttpResponseServerError

from otree import common_internal


# =============================================================================
# MIDDLEWARES
# =============================================================================

class CheckDBMiddleware(object):

    checked = False

    def process_request(self, request):
        if not CheckDBMiddleware.checked:
            CheckDBMiddleware.checked = common_internal.db_status_ok()
            if not CheckDBMiddleware.checked:
                msg = "Your DB is not ready. Try resetting the database."
                return HttpResponseServerError(msg)


class HumanErrorMiddleware(object):

    def process_exception(self, request, exception):
        common_internal.reraise(exception)
