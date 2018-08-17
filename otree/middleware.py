#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTS
# =============================================================================

from django.http import HttpResponseServerError

from otree.common_internal import missing_db_tables


class CheckDBMiddleware:
    synced = None

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not CheckDBMiddleware.synced:
            # very fast, 0.01-0.02 seconds for the whole check
            missing_tables = missing_db_tables()
            if missing_tables:
                listed_tables = missing_tables[:3]
                unlisted_tables = missing_tables[3:]
                msg = (
                    "Your database is not ready. Try running 'otree resetdb'. "
                    "(Missing tables for {}, and {} other models). "
                ).format(
                    ', '.join(listed_tables), len(unlisted_tables))
                return HttpResponseServerError(msg)
            else:
                CheckDBMiddleware.synced = True
        return self.get_response(request)
