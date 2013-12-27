__doc__ = """This module contains views for ajax calls from ajax change list pages
"""
import urllib
import cgi
import json
from django.utils import six

from django.conf import settings

from django.contrib import admin
from django.contrib.admin import options
from django.http import HttpResponse

from ptree.templatetags import ajax_admin_list


# NOTE: this function has been adapted from django.contrib.admin.options.ModelAdmin.changelist_view of Django 1.6. 
# It may NOT work with other version of Django.
def get_cl(request, model_admin):
    from django.contrib.admin.views.main import ERROR_FLAG
    opts = model_admin.model._meta
    app_label = opts.app_label
    # TODO
    #if not model_admin.has_change_permission(request, None):
    #    raise PermissionDenied

    list_display = model_admin.get_list_display(request)
    list_display_links = model_admin.get_list_display_links(request, list_display)
    list_filter = model_admin.get_list_filter(request)

    # Check actions to see if any are available on this changelist
    actions = model_admin.get_actions(request)
    if actions:
        # Add the action checkboxes if there are any actions available.
        list_display = ['action_checkbox'] + list(list_display)

    ChangeList = model_admin.get_changelist(request)
    try:
        cl = ChangeList(request, model_admin.model, list_display,
            list_display_links, list_filter, model_admin.date_hierarchy,
            model_admin.search_fields, model_admin.list_select_related,
            model_admin.list_per_page, model_admin.list_max_show_all, model_admin.list_editable,
            model_admin)
    except options.IncorrectLookupParameters:
        pass
        # Wacky lookup parameters were given, so redirect to the main
        # changelist page, without parameters, and pass an 'invalid=1'
        # parameter via the query string. If wacky parameters were given
        # and the 'invalid=1' parameter was already in the query string,
        # something is screwed up with the database, so display an error
        # page.
        # TODO: handle this error
        #if ERROR_FLAG in request.GET.keys():
        #    return SimpleTemplateResponse('admin/invalid_setup.html', {
        #        'title': _('Database error'),
        #    })
        #return HttpResponseRedirect(request.path + '?' + ERROR_FLAG + '=1')

    # If we're allowing changelist editing, we need to construct a formset
    # for the changelist given all the fields to be edited. Then we'll
    # use the formset to validate/process POSTed data.
    formset = cl.formset = None

    # Handle GET -- construct a formset for display.
    if cl.list_editable:
        FormSet = model_admin.get_changelist_formset(request)
        formset = cl.formset = FormSet(queryset=cl.result_list)

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
admin.autodiscover()
url_name2model_admin = None
def get_model_admin_from(url_name):
    # TODO error handling
    global url_name2model_admin
    if url_name2model_admin is None:
        url_name2model_admin = {}
        for model, model_admin in six.iteritems(admin.site._registry):
            url_name2model_admin['%s_%s_changelist' % (model._meta.app_label, model._meta.model_name)] = model_admin
    return url_name2model_admin[url_name]


# TODO: admin priveledge only
def ajax_ptree_change_list_results(request):
    #TODO
    url_name = request.GET["url_name"]
    get_params_str = request.GET["get_params"]
    parsed_qs = cgi.parse_qs(get_params_str)
    for key in parsed_qs.keys():
        parsed_qs[key] = parsed_qs[key][0]
    model_admin = get_model_admin_from(url_name)
    resolver_match = FakeResolverMatch(app_name="admin", url_name=url_name)
    fake_request = FakeRequest(resolver_match, parsed_qs, request.user)
    cl = get_cl(fake_request, model_admin)
    _, results_json = ajax_admin_list.prepare_results_json(cl)
    return HttpResponse(results_json)
