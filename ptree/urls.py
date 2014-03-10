from django.conf.urls import *
from django.utils.importlib import import_module
import inspect
import vanilla
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.contrib import admin
from django.core.urlresolvers import reverse
from django.views.generic.base import RedirectView



def url_patterns_from_module(module_name):
    """automatically generates URLs for all Views in the module,
    So that you don't need to enumerate them all in urlpatterns.
    URLs take the form "gamename/ViewName". See the method url_pattern() for more info

    So call this function in your urls.py and pass it the names of all Views modules as strings.
    """

    views_module = import_module(module_name)

    all_views = [ViewClass for (_, ViewClass) in inspect.getmembers(views_module, 
                lambda m: inspect.isclass(m) and \
                issubclass(m, vanilla.View) and \
                inspect.getmodule(m) == views_module)]

    view_urls = []

    for View in all_views:
        if hasattr(View, 'url_pattern'):
            the_url = url(View.url_pattern(), View.as_view())
            view_urls.append(the_url)

    return patterns('', *view_urls)

def augment_urlpatterns(urlpatterns):

    urlpatterns += patterns(
        '',
        url(r'^$', RedirectView.as_view(url='/admin')),
        url(r'^admin/', include(admin.site.urls)),
        url(r'^export/(\w+)/$', 'ptree.views.export.export', name='ptree_views_export_export'),
        url(r'^export-list/$', 'ptree.views.export.export_list', name='ptree_views_export_export_list'),
        url(r'^export-docs/(\w+)/$', 'ptree.views.export.export_docs', name='ptree_views_export_export_docs'),
    )
    urlpatterns += staticfiles_urlpatterns()
    for app_name in settings.INSTALLED_PTREE_APPS:
        views_module_name = '{}.views'.format(app_name)
        utilities_module_name = '{}.utilities'.format(app_name)
        urlpatterns += url_patterns_from_module(views_module_name)
        urlpatterns += url_patterns_from_module(utilities_module_name)
    urlpatterns += url_patterns_from_module('ptree.views.concrete')
    #urlpatterns += url_patterns_from_module('ptree.views.ajax_change_list')
    urlpatterns += patterns(
        'ptree.views.ajax_change_list',
        url(r'^ajax/ptree-change-list-results/$', 'ajax_ptree_change_list_results', name='ajax_ptree_change_list_results'),
    )

    return urlpatterns
