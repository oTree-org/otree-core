from django.conf.urls import *
import ptree.views.concrete
from django.utils.importlib import import_module
import inspect
import vanilla
from django.conf import settings
import ptree.settings

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

        the_url = url(View.url_pattern(), View.as_view())
        view_urls.append(the_url)

    return patterns('', *view_urls)



def urlpatterns():
    p = patterns('', url(r'^exports/', include('data_exports.urls', namespace='data_exports')))
    for app_name in ptree.settings.get_ptree_apps(settings.USER_PTREE_EXPERIMENT_APPS,
                                                  settings.USER_PTREE_NON_EXPERIMENT_APPS):
        views_module_name = '{}.views'.format(app_name)
        p += url_patterns_from_module(views_module_name)
    p += url_patterns_from_module('ptree.views.concrete')

    return p