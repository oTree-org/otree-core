#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""This module contains views for ajax calls from ajax change list pages

"""


# =============================================================================
# IMPORTS
# =============================================================================

import urllib
import cgi

from django.utils import six
from django.contrib import admin
from django.contrib.admin import options
from django.http import HttpResponse

from otree.templatetags import ajax_admin_list


def get_cl(request, model_admin):
    # from django.contrib.admin.views.main import ERROR_FLAG

    # TODO
    # if not model_admin.has_change_permission(request, None):
    #    raise PermissionDenied

    list_display = model_admin.get_list_display(request)
    list_display_links = model_admin.get_list_display_links(
        request, list_display
    )
    list_filter = model_admin.get_list_filter(request)

    # Check actions to see if any are available on this changelist
    actions = model_admin.get_actions(request)
    if actions:
        # Add the action checkboxes if there are any actions available.
        list_display = ['action_checkbox'] + list(list_display)

    ChangeList = model_admin.get_changelist(request)
    try:
        cl = ChangeList(
            request, model_admin.model, list_display,
            list_display_links, list_filter, model_admin.date_hierarchy,
            model_admin.search_fields, model_admin.list_select_related,
            model_admin.list_per_page, model_admin.list_max_show_all,
            model_admin.list_editable, model_admin
        )
    except options.IncorrectLookupParameters:
        pass
        # Wacky lookup parameters were given, so redirect to the main
        # changelist page, without parameters, and pass an 'invalid=1'
        # parameter via the query string. If wacky parameters were given
        # and the 'invalid=1' parameter was already in the query string,
        # something is screwed up with the database, so display an error
        # page.
        # TODO: handle this error
        # if ERROR_FLAG in request.GET.keys():
        #    return SimpleTemplateResponse('admin/invalid_setup.html', {
        #        'title': _('Database error'),
        #    })
        # return HttpResponseRedirect(request.path + '?' + ERROR_FLAG + '=1')

    # If we're allowing changelist editing, we need to construct a formset
    # for the changelist given all the fields to be edited. Then we'll
    # use the formset to validate/process POSTed data.
    cl.formset = None

    # Handle GET -- construct a formset for display.
    if cl.list_editable:
        FormSet = model_admin.get_changelist_formset(request)
        cl.formset = FormSet(queryset=cl.result_list)

    return cl


class FakeResolverMatch:
    def __init__(self, app_name, url_name):
        self.app_name = app_name
        self.url_name = url_name


class FakeGET(dict):
    def urlencode(self):
        return urllib.urlencode(self)


class FakeRequest:
    def __init__(self, resolver_match, get_params, user):
        self.GET = FakeGET()
        self.GET.update(get_params)
        self.resolver_match = resolver_match
        self.user = user


# TODO
# 2014-3-11: chris changed this to use otree's custom autodiscover
from otree.adminlib import autodiscover
autodiscover()
url_name2model_admin = None


def get_model_admin_from(url_name):
    # TODO error handling
    global url_name2model_admin
    if url_name2model_admin is None:
        url_name2model_admin = {}
        for model, model_admin in six.iteritems(admin.site._registry):
            url_name2model_admin[
                '{}_{}_changelist'.format(model._meta.app_label,
                                          model._meta.model_name)
            ] = model_admin
    return url_name2model_admin[url_name]


# TODO: admin priveledge only
def ajax_otree_change_list_results(request):
    # TODO
    url_name = request.GET["url_name"]
    get_params_str = request.GET["get_params"]
    parsed_qs = cgi.parse_qs(get_params_str, keep_blank_values=True)
    for key in parsed_qs.keys():
        parsed_qs[key] = parsed_qs[key][0]
    model_admin = get_model_admin_from(url_name)
    resolver_match = FakeResolverMatch(app_name="admin", url_name=url_name)
    fake_request = FakeRequest(resolver_match, parsed_qs, request.user)
    cl = get_cl(fake_request, model_admin)
    _, results_json = ajax_admin_list.prepare_results_json(cl)
    return HttpResponse(results_json)
