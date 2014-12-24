#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.template import Library
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from .. import common_internal


# =============================================================================
# CONSTANTS
# =============================================================================

register = Library()

SUBSESSION_APP_MODELS_ORDER = ["Subsession", "Group", "Player"]
SESSION_APP_MODELS_ORDER = ["Session", "Participant"]


# =============================================================================
# FUNCTIONS
# =============================================================================

def _get_model_position(object_name, model_order_list):
    try:
        position = model_order_list.index(object_name)
    except ValueError:
        position = -1
    return position


def sort_models(models, model_order_list):
    def mcmp(a, b):
        return cmp(_get_model_position(a["object_name"], model_order_list),
                   _get_model_position(b["object_name"], model_order_list))
    models.sort(mcmp)
    return models


def fix_subsession_app_models_order(models):
    models = [model for model in models]
    return sort_models(models, SUBSESSION_APP_MODELS_ORDER)


def fix_session_app_models_order(models):
    models = [model for model in models]
    return sort_models(models, SESSION_APP_MODELS_ORDER)


def is_subsession_app(app):
    return common_internal.is_subsession_app(app["app_label"])


def app_sequence_only(apps):
    return [
        app for app in apps
        if common_internal.is_subsession_app(app["app_label"])
    ]


def non_app_sequence(apps):
    return [
        app for app in apps
        if not common_internal.is_subsession_app(app["app_label"])
    ]


@register.inclusion_tag('admin/_dashboard_app_template.html',
                        takes_context=True)
def mock_data_export_app(context):
    context["app"] = {
        "app_label": "_builtin", "app_url": "", "name": _("_builtin"),
        "dont_link_app_name": True,
        "models": [{
            "object_name": "dataexport",
            "name": _("Data Export"),
            "admin_url": reverse("otree_views_export_export_list")
        }]
    }
    context["app_models"] = context["app"]["models"]
    return context


register.filter('fix_subsession_app_models_order',
                fix_subsession_app_models_order)
register.filter('fix_session_app_models_order', fix_session_app_models_order)
register.filter('app_sequence_only', app_sequence_only)
register.filter('non_app_sequence', non_app_sequence)
register.filter('app_name_format', common_internal.app_name_format)
