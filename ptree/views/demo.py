from django.shortcuts import get_object_or_404, render_to_response
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
import vanilla
import ptree.constants as constants
from ptree.sessionlib.models import Session
from ptree.session import create_session, demo_enabled_session_types, session_types_as_dict
import threading

class DemoIndex(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^demo/$'

    def get(self, *args, **kwargs):
        session_info = []
        session_types = session_types_as_dict()
        for type in demo_enabled_session_types():
            session_info.append(
                {
                    'type': type,
                    'url': '/demo/{}/'.format(type),
                    'doc': session_types[type].doc or ''
                }
            )
        return render_to_response('ptree/demo.html', {'session_info': session_info})

def ensure_enough_spare_sessions(type):
    DESIRED_SPARE_SESSIONS = 3

    spare_sessions = Session.objects.filter(
        special_category=constants.special_category_demo,
        type=type,
        demo_already_used=False,
    ).count()

    # fill in whatever gap exists. want at least 3 sessions waiting.
    for i in range(DESIRED_SPARE_SESSIONS - spare_sessions):
        print 'Creating demo sessions: {}'.format(type)
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

class Demo(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^demo/(?P<session_type>\w+)/$'

    def get(self, *args, **kwargs):
        type=kwargs['session_type']

        if self.request.is_ajax():
            session = get_session(type)
            return HttpResponse(int(session is not None))

        t = threading.Thread(
            target=ensure_enough_spare_sessions,
            args=(type,)
        )
        t.start()

        session = get_session(type)
        if session:
            session.demo_already_used = True
            session.save()


            return render_to_response(
                'ptree/admin/StartLinks.html',
                {
                    'experimenter_url': self.request.build_absolute_uri(session.session_experimenter._start_url()),
                    'participant_urls': [self.request.build_absolute_uri(participant._start_url()) for participant in session.participants()],
                }
            )
        else:
            return render_to_response(
                'ptree/WaitPage.html',
                {
                    'SequenceViewURL': self.request.path,
                    'wait_page_title_text': 'Please wait',
                    'wait_page_body_text': 'Creating a session.',
                }
            )