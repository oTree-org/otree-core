#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTS
# =============================================================================

from django.http import HttpResponseServerError

from otree.common_internal import db_status_ok

class CheckDBMiddleware(object):

    def process_request(self, request):
        synced = db_status_ok(cache=True)
        if not synced:
            msg = "Your database is not ready. Try running 'otree resetdb'."
            return HttpResponseServerError(msg)


