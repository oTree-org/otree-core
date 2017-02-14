#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTS
# =============================================================================

from django.http import HttpResponseServerError

from otree.common_internal import missing_db_table


class CheckDBMiddleware(object):

    synced = None

    def process_request(self, request):
        if not CheckDBMiddleware.synced:
            missing_table = missing_db_table()
            if missing_table:
                print(missing_table, type(missing_table))
                msg = ("Your database is not ready "
                       "(missing table for model {}). "
                       "Try running 'otree resetdb'.").format(missing_table)
                return HttpResponseServerError(msg)
            else:
                CheckDBMiddleware.synced = True
