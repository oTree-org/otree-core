from django.shortcuts import get_object_or_404, render_to_response
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
import vanilla
import ptree.constants as constants
from ptree.sessionlib.models import Session
from ptree.session import create_session, session_types_as_dict, demo_enabled_session_types
import threading
import time
import urllib
from ptree.common import get_session_module, get_models_module, app_name_format

def escaped_start_link_url(session_type_name):
    return '/demo/{}/'.format(urllib.quote_plus(session_type_name))

class DemoIndex(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^demo/$'

    def get(self, *args, **kwargs):

        intro_text = getattr(get_session_module(), 'demo_page_intro_text', '')

        session_info = []
        for session_type in demo_enabled_session_types():
            session_info.append(
                {
                    'type': session_type.name,
                    'url': escaped_start_link_url(session_type.name),
                    'doc': session_type.doc or '',
                    'subsession_apps': ', '.join([app_name_format(app_name) for app_name in session_type.subsession_apps]),
                }
            )
        return render_to_response('ptree/demo/index.html', {'session_info': session_info, 'intro_text': intro_text})

def ensure_enough_spare_sessions(type):
    time.sleep(5)
    DESIRED_SPARE_SESSIONS = 3

    spare_sessions = Session.objects.filter(
        special_category=constants.special_category_demo,
        type=type,
        demo_already_used=False,
    ).count()


    # fill in whatever gap exists. want at least 3 sessions waiting.
    for i in range(DESIRED_SPARE_SESSIONS - spare_sessions):
        create_session(
            special_category=constants.special_category_demo,
            type=type
        )

def get_session(type):

    sessions = Session.objects.filter(
        special_category=constants.special_category_demo,
        type=type,
        demo_already_used=False,
        ready=True,
    )
    if sessions.exists():
        return sessions[:1].get()

def info_about_session_type(session_type_name):
    session_type = session_types_as_dict()[session_type_name]
    subsession_apps = []
    for app_name in session_type.subsession_apps:
        models_module = get_models_module(app_name)
        doc = getattr(models_module, 'doc', '')
        subsession_apps.append(
            {
                'name': app_name_format(app_name),
                'doc': doc,
            }
        )
    return {
        'doc': session_type.doc,
        'subsession_apps': subsession_apps,
    }

def render_to_start_links_page(request, session, is_demo_page):

    context_data = {
            'session_type_name': session.type,
            'experimenter_url': request.build_absolute_uri(session.session_experimenter._start_url()),
            'participant_urls': [request.build_absolute_uri(participant._start_url()) for participant in session.participants()],
            'is_demo_page': is_demo_page,
    }

    context_data.update(info_about_session_type(session.type))

    return render_to_response(
        'ptree/admin/StartLinks.html',
        context_data
    )

class Demo(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^demo/(?P<session_type>.+)/$"

    def get(self, *args, **kwargs):
        session_type_name=urllib.unquote_plus(kwargs['session_type'])

        if session_type_name in session_types_as_dict().keys():
            if not session_type_name in [st.name for st in demo_enabled_session_types()]:
                return HttpResponseNotFound('Session type "{}" not enabled for demo'.format(session_type_name))
        else:
            return HttpResponseNotFound('Session type "{}" not found'.format(session_type_name))

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
            return render_to_response(
                'ptree/WaitPage.html',
                {
                    'SequenceViewURL': escaped_start_link_url(session_type_name),

                    'wait_page_title_text': 'Please wait',
                    'wait_page_body_text': 'Creating a session.',
                }
            )