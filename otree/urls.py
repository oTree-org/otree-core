#!/usr/bin/env python
# -*- coding: utf-8 -*-

import inspect
from importlib import import_module

from django.conf import urls

from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic.base import RedirectView
from django.conf import settings
from django.contrib.auth.decorators import login_required
from otree.views.rest import SessionParticipantsList, Ping

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
    # see issue #303 for discussion of granting access with "white-list"
    # 2015-11-13: EXPERIMENT deprecated, renamed to STUDY
    # remove EXPERIMENT eventually
    if (
            settings.AUTH_LEVEL in {'DEMO', 'EXPERIMENT', 'STUDY'} and
            module_name.startswith('otree.views')):
        unrestricted_views = {
            'otree.views.concrete.AssignVisitorToDefaultSession',
            'otree.views.concrete.InitializeParticipant',
            'otree.views.concrete.MTurkLandingPage',
            'otree.views.concrete.MTurkStart',
            'otree.views.concrete.JoinSessionAnonymously',
            'otree.views.concrete.OutOfRangeNotification',
            'otree.views.concrete.WaitUntilAssignedToGroup',
        }

        if settings.AUTH_LEVEL == 'DEMO':
            unrestricted_views.update({
                'otree.views.concrete.AdvanceSession',
                'otree.views.demo.CreateDemoSession',
                'otree.views.demo.DemoIndex',
                'otree.views.demo.SessionFullscreen',
                'otree.views.admin.SessionDescription',
                'otree.views.admin.SessionMonitor',
                'otree.views.admin.SessionPayments',
                'otree.views.admin.SessionResults',
                'otree.views.admin.SessionStartLinks',
            })
    else:
        unrestricted_views = [
            '%s.%s' % (module_name, view.__name__) for view in all_views
        ]

    view_urls = []
    for ViewCls in all_views:
        if '%s.%s' % (module_name, ViewCls.__name__) in unrestricted_views:
            as_view = ViewCls.as_view()
        else:
            as_view = login_required(ViewCls.as_view())

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
        urls.url(r'^$', RedirectView.as_view(url='/demo', permanent=True)),
        urls.url(
            r'^accounts/login/$',
            'django.contrib.auth.views.login',
            {'template_name': 'otree/login.html'},
            name='login_url',
        ),
        urls.url(
            r'^accounts/logout/$',
            'django.contrib.auth.views.logout',
            {'next_page': 'demo_index'},
            name='logout',
        ),
    )

    rest_api_urlpatterns = (
        urls.url(r'^ping/$', Ping.as_view(), name="ping"),
        urls.url(
            r'^sessions/(?P<session_code>[a-z]+)/participants/$',
            SessionParticipantsList.as_view(),
            name="session_participants_list")
    )
    urlpatterns += rest_api_urlpatterns

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
    urlpatterns += url_patterns_from_module('otree.views.export')

    return urlpatterns
