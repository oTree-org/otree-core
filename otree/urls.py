#!/usr/bin/env python
# -*- coding: utf-8 -*-

import inspect

from django.conf import urls
from django.utils.importlib import import_module

from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic.base import RedirectView
from django.conf import settings
from django.contrib.auth.decorators import login_required

from otree.common_internal import get_models_module


def url_patterns_from_module(module_name):
    """automatically generates URLs for all Views in the module,
    So that you don't need to enumerate them all in urlpatterns.
    URLs take the form "gamename/ViewName".
    See the method url_pattern() for more info

    So call this function in your urls.py and pass it the names of all
    Views modules as strings.

    """

    views_module = import_module(module_name)

    all_views = [
        ViewCls for _, ViewCls in inspect.getmembers(views_module)
        if hasattr(ViewCls, 'url_pattern') and
        inspect.getmodule(ViewCls) == views_module
    ]

    # see issue #273 for discussion of AUTH_LEVEL setting
    if settings.DEBUG and settings.AUTH_LEVEL not in ['DEMO', 'EXPERIMENT']:
        AUTH_LEVEL = 'FULL'
    elif not settings.DEBUG and settings.AUTH_LEVEL not in ['DEMO',
                                                            'EXPERIMENT']:
        AUTH_LEVEL = 'EXPERIMENT'
    else:
        AUTH_LEVEL = settings.AUTH_LEVEL

    restricted_views_demo = ['SessionTypesToCreate', 'CreateSession',
                             'AdminHome', 'MTurkInfo', 'PersistentLabURLs']

    restricted_views_experiment = restricted_views_demo + [
        'SessionDescription', 'SessionMonitor', 'SessionResults',
        'SessionStartLinks', 'SessionPayments',
        'DemoIndex', 'CreateDemoSession'
    ]
    if AUTH_LEVEL == 'DEMO':
        restricted_views = restricted_views_demo
    elif AUTH_LEVEL == 'EXPERIMENT':
        restricted_views = restricted_views_experiment
    else:
        restricted_views = []

    view_urls = []
    for ViewCls in all_views:
        if ViewCls.__name__ in restricted_views:
            as_view = login_required(ViewCls.as_view())
        else:
            as_view = ViewCls.as_view()

        if hasattr(ViewCls, 'url_name'):
            view_urls.append(
                urls.url(ViewCls.url_pattern(), as_view,
                         name=ViewCls.url_name())
            )
        else:
            view_urls.append(urls.url(ViewCls.url_pattern(), as_view))

    return urls.patterns('', *view_urls)


def augment_urlpatterns(urlpatterns):

    urlpatterns += urls.patterns(
        '',
        urls.url(r'^$', RedirectView.as_view(url='/demo'), name='demo'),
        urls.url(
            r'^accounts/login/$', 'django.contrib.auth.views.login',
            {'template_name': 'otree/login.html'}
        ),
    )

    urlpatterns += staticfiles_urlpatterns()

    used_names_in_url = set()
    for app_name in settings.INSTALLED_OTREE_APPS:
        models_module = get_models_module(app_name)
        name_in_url = models_module.Constants.name_in_url
        if name_in_url in used_names_in_url:
            msg = (
                "App {} has name_in_url='{}', "
                "which is already used by another app"
            ).format(app_name, name_in_url)
            raise ValueError(msg)

        used_names_in_url.add(name_in_url)
        views_module_name = '{}.views'.format(app_name)
        utilities_module_name = '{}._builtin'.format(app_name)
        urlpatterns += url_patterns_from_module(views_module_name)
        urlpatterns += url_patterns_from_module(utilities_module_name)

    urlpatterns += url_patterns_from_module('otree.views.concrete')
    urlpatterns += url_patterns_from_module('otree.views.demo')
    urlpatterns += url_patterns_from_module('otree.views.admin')
    urlpatterns += url_patterns_from_module('otree.views.mturk')

    return urlpatterns
