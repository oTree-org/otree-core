# -*- coding: utf-8 -*-
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
import vanilla
import otree.constants as constants
from otree.session.models import Session
from otree.session import create_session, session_types_dict, session_types_list
import threading
import time
import urllib
from otree.common_internal import get_session_module, get_models_module, app_name_format
from django.conf import settings

def start_link_url(session_type_name):
    return '/demo/{}/'.format(session_type_name)

class DemoIndex(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^demo/$'

    def get(self, *args, **kwargs):

        intro_text = getattr(get_session_module(), 'demo_page_intro_text', '')

        session_info = []
        for session_type in session_types_list(demo_only=True):
            session_info.append(
                {
                    'name': session_type.name,
                    'display_name': session_type.display_name,
                    'url': start_link_url(session_type.name),
                    'num_demo_parcitipants': session_type.num_demo_participants
                }
            )
        return TemplateResponse(
            self.request,
            'otree/demo/index.html',
            {'session_info': session_info, 'intro_text': intro_text, 'debug': settings.DEBUG}
        )

def ensure_enough_spare_sessions(type_name):
    time.sleep(5)
    DESIRED_SPARE_SESSIONS = 3

    spare_sessions = Session.objects.filter(
        special_category=constants.special_category_demo,
        type_name=type_name,
        demo_already_used=False,
    ).count()


    # fill in whatever gap exists. want at least 3 sessions waiting.
    for i in range(DESIRED_SPARE_SESSIONS - spare_sessions):
        create_session(
            special_category=constants.special_category_demo,
            type_name=type_name,
            preassign_players_to_groups=True,
        )


def get_session(type_name):

    sessions = Session.objects.filter(
        special_category=constants.special_category_demo,
        type_name=type_name,
        demo_already_used=False,
        ready=True,
    )
    if sessions.exists():
        return sessions[:1].get()

def info_about_session_type(session_type):

    subsession_apps = []
    for app_name in session_type.subsession_apps:
        models_module = get_models_module(app_name)
        num_rounds = models_module.Constants.number_of_rounds
        doc = getattr(models_module, 'doc', '')
        formatted_app_name = app_name_format(app_name)
        if num_rounds > 1:
            formatted_app_name = '{} ({} rounds)'.format(formatted_app_name, num_rounds)
        subsession_apps.append(
            {
                'name': formatted_app_name,
                'doc': doc,
            }
        )
    return {
        'doc': session_type.doc,
        'subsession_apps': subsession_apps,
    }

def render_to_start_links_page(request, session, is_demo_page):

    context_data = {
            'display_name': session.type().display_name,
            'experimenter_url': request.build_absolute_uri(session.session_experimenter._start_url()),
            'participant_urls': [request.build_absolute_uri(participant._start_url()) for participant in session.get_participants()],
            'is_demo_page': is_demo_page,
    }

    session_type = session_types_dict(demo_only=True)[session.type_name]
    context_data.update(info_about_session_type(session_type))

    return TemplateResponse(
        request,
        'otree/admin/StartLinks.html',
        context_data
    )

class Demo(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^demo/(?P<session_type>.+)/$"

    def get(self, *args, **kwargs):
        session_type_name=kwargs['session_type']

        session_dir = session_types_dict(demo_only=True)
        try:
            session_dir[session_type_name]
        except KeyError:
            return HttpResponseNotFound('Session type "{}" not found, or not enabled for demo'.format(session_type_name))

        if self.request.is_ajax():
            session = get_session(session_type_name)
            return HttpResponse(int(session is not None))

        t = threading.Thread(
            target=ensure_enough_spare_sessions,
            args=(session_type_name,)
        )
        t.start()

        session = get_session(session_type_name)
        if session:
            session.demo_already_used = True
            session.save()

            return render_to_start_links_page(self.request, session, is_demo_page=True)
        else:
            return TemplateResponse(
                self.request,
                'otree/WaitPage.html',
                {
                    'SequenceViewURL': start_link_url(session_type_name),

                    'title_text': 'Please wait',
                    'body_text': 'Creating a session.',
                }
            )
