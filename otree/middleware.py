#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTS
# =============================================================================

from django.http import HttpResponseServerError
from django.conf import settings

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


class DebugTableMiddleware(object):

    def process_template_response(self, request, response):
        if settings.DEBUG:
            view = response.context_data.get("view", None)
            debug_values = []
            if view and hasattr(view, "get_debug_values"):
                view_debug_values = view.get_debug_values() or []
                debug_values += view_debug_values
            if view and hasattr(view, "on_debug_show"):
                view_custom_debug_values = view.on_debug_show() or {}
                debug_values += sorted(view_custom_debug_values.items())
            response.context_data["DEBUG_TABLE"] = debug_values
        return response
