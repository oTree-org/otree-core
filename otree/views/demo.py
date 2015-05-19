# -*- coding: utf-8 -*-

import threading
import time

from django.conf import settings
from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404

import vanilla

import otree.constants as constants
from otree.views.abstract import GenericWaitPageMixin
from otree.models.session import Session
from otree.session import (
    create_session, get_session_types_dict, get_session_types_list
)

# if it's debug mode, we should always generate a new session
# because a bug might have been fixed
# in production, we optimize for UX and quick loading
DESIRED_SPARE_SESSIONS = 1 if settings.DEBUG else 3


class DemoIndex(vanilla.TemplateView):

    template_name = 'otree/demo/index.html'

    @classmethod
    def url_pattern(cls):
        return r'^demo/$'

    @classmethod
    def url_name(cls):
        return 'demo_index'

    def get_context_data(self, **kwargs):

        intro_text = settings.DEMO_PAGE_INTRO_TEXT
        context = super(DemoIndex, self).get_context_data(**kwargs)

        session_info = []
        for session_type in get_session_types_list():
            session_info.append(
                {
                    'name': session_type['name'],
                    'display_name': session_type['display_name'],
                    'url': reverse(
                        'create_demo_session', args=(session_type['name'],)
                    ),
                    'num_demo_participants': session_type[
                        'num_demo_participants'
                    ]
                }
            )

        context.update({
            'session_info': session_info,
            'intro_text': intro_text,
            'is_debug': settings.DEBUG
        })
        return context


def ensure_enough_spare_sessions(session_type_name):

    # hack: this sleep is to prevent locks on SQLite. This gives time to let
    # the page request finish before create_session is called, because creating
    # the session involves a lot of database I/O, which seems to cause locks
    # when multiple threads access at the same time.
    time.sleep(5)

    spare_sessions = Session.objects.filter(
        special_category=constants.session_special_category_demo,
        demo_already_used=False,
    )
    spare_sessions = [
        s for s in spare_sessions
        if s.session_type['name'] == session_type_name
    ]

    # fill in whatever gap exists. want at least 3 sessions waiting.
    for i in range(DESIRED_SPARE_SESSIONS - len(spare_sessions)):
        create_session(
            special_category=constants.session_special_category_demo,
            session_type_name=session_type_name,
        )


def get_session(session_type_name):

    sessions = Session.objects.filter(
        special_category=constants.session_special_category_demo,
        demo_already_used=False,
        ready=True,
    )
    sessions = [
        s for s in sessions
        if s.session_type['name'] == session_type_name
    ]
    if len(sessions):
        return sessions[0]


class CreateDemoSession(GenericWaitPageMixin, vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^demo/(?P<session_type>.+)/$"

    @classmethod
    def url_name(cls):
        return 'create_demo_session'

    def _is_ready(self):
        session = get_session(self.session_type_name)
        return bool(session)

    def _before_returning_wait_page(self):
        session_types = get_session_types_dict()
        try:
            session_types[self.session_type_name]
        except KeyError:
            msg = (
                "Session type '{}' not found, or not enabled for demo"
            ).format(self.session_type_name)
            raise Http404(msg)

        t = threading.Thread(
            target=ensure_enough_spare_sessions,
            args=(self.session_type_name,)
        )
        t.start()

    def body_text(self):
        return 'Creating a session'

    def _response_when_ready(self):
        session = get_session(self.session_type_name)
        session.demo_already_used = True
        session.save()

        if 'fullscreen' in self.request.GET and self.request.GET['fullscreen']:
            landing_url = reverse('session_fullscreen', args=(session.pk,))
        else:
            landing_url = reverse('session_start_links', args=(session.pk,))
        return HttpResponseRedirect(landing_url)

    def dispatch(self, request, *args, **kwargs):
        self.session_type_name = kwargs['session_type']
        return super(CreateDemoSession, self).dispatch(
            request, *args, **kwargs
        )

    def _get_wait_page(self):
        return TemplateResponse(
            self.request, 'otree/WaitPage.html', {'view': self}
        )


class SessionFullscreen(vanilla.TemplateView):
    '''Launch the session in fullscreen mode
    '''

    template_name = 'otree/demo/SessionFullscreen.html'

    @classmethod
    def url_name(cls):
        return 'session_fullscreen'

    @classmethod
    def url_pattern(cls):
        return r"^SessionFullscreen/(?P<pk>\d+)/$"

    def dispatch(self, request, *args, **kwargs):
        session_pk = int(kwargs['pk'])
        self.session = get_object_or_404(Session, pk=session_pk)
        return super(SessionFullscreen, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, **kwargs):
        context = super(SessionFullscreen, self).get_context_data(**kwargs)
        participant_urls = [
            self.request.build_absolute_uri(participant._start_url())
            for participant in self.session.get_participants()
        ]
        context.update({
            'session': self.session,
            'participant_urls': participant_urls
        })
        return context
