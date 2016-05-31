#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTS
# =============================================================================

from django.http import HttpResponseServerError

from otree.common_internal import db_status_ok

class CheckDBMiddleware(object):

    def process_request(self, request):
        synced = db_status_ok(cached_per_process=True)
        if not synced:
            msg = "Your DB is not ready. Try resetting the database."
            return HttpResponseServerError(msg)


