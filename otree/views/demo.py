# -*- coding: utf-8 -*-

import threading
import time

from django.conf import settings
from django.http import HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404

import vanilla
import channels

import otree.constants_internal as constants
from otree.views.abstract import GenericWaitPageMixin
from otree.models.session import Session
from otree.session import (
    create_session, SESSION_CONFIGS_DICT
)
import otree.session
from otree.common_internal import channels_create_demo_session_group_name
from six.moves import range

# if it's debug mode, we should always generate a new session
# because a bug might have been fixed
# in production, we optimize for UX and quick loading
MAX_SESSIONS_TO_CREATE = 1 if settings.DEBUG else 3


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
        for session_config in SESSION_CONFIGS_DICT.values():
            session_info.append(
                {
                    'name': session_config['name'],
                    'display_name': session_config['display_name'],
                    'url': reverse(
                        'create_demo_session', args=(session_config['name'],)
                    ),
                    'num_demo_participants': session_config[
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


def ensure_enough_spare_sessions(session_config_name):

    # hack: this sleep is to prevent locks on SQLite. This gives time to let
    # the page request finish before create_session is called, because creating
    # the session involves a lot of database I/O, which seems to cause locks
    # when multiple threads access at the same time.
    if settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
        time.sleep(5)

    spare_sessions = Session.objects.filter(
        special_category=constants.session_special_category_demo,
        demo_already_used=False,
    )
    spare_sessions = [
        s for s in spare_sessions
        if s.config['name'] == session_config_name
    ]

    # fill in whatever gap exists. want at least 3 sessions waiting.
    for i in range(MAX_SESSIONS_TO_CREATE - len(spare_sessions)):
        create_session(
            special_category=constants.session_special_category_demo,
            session_config_name=session_config_name,
        )


def get_session(session_config_name):

    sessions = Session.objects.filter(
        special_category=constants.session_special_category_demo,
        demo_already_used=False,
        ready=True,
    )
    sessions = [
        s for s in sessions
        if s.config['name'] == session_config_name
    ]
    if len(sessions):
        return sessions[0]


class CreateDemoSession(GenericWaitPageMixin, vanilla.GenericView):

    @classmethod
    def url_pattern(cls):
        return r"^demo/(?P<session_config>.+)/$"

    @classmethod
    def url_name(cls):
        return 'create_demo_session'

    body_text = 'Creating a session'

    def _is_ready(self):
        self.session = get_session(self.session_config_name)
        return bool(self.session)

    def _before_returning_wait_page(self):
        try:
            session_config = SESSION_CONFIGS_DICT[self.session_config_name]
        except KeyError:
            msg = (
                "Session config '{}' not found"
            ).format(self.session_config_name)
            raise Http404(msg)
        # check that it divides evenly
        # need to check here so that the user knows upfront
        session_lcm = otree.session.get_lcm(session_config)
        num_participants = session_config['num_demo_participants']
        if num_participants % session_lcm:
            msg = (
                'Session Config {}: Number of participants ({}) does not '
                'divide evenly into group size ({})'
            ).format(
                self.session_config_name,
                num_participants,
                session_lcm
            )
            raise Http404(msg)

        kwargs = {
            'special_category': constants.session_special_category_demo,
            'session_config_name': self.session_config_name,
        }

        channels_group_name = channels_create_demo_session_group_name(
            self.session_config_name)
        channels.Channel('otree.create_session').send({
            'kwargs': kwargs,
            'channels_group_name': channels_group_name
        })

    def _response_when_ready(self):
        session = self.session
        session.demo_already_used = True
        session.save()

        if 'fullscreen' in self.request.GET and self.request.GET['fullscreen']:
            landing_url = reverse('session_fullscreen', args=(session.pk,))
        else:
            landing_url = reverse('session_start_links', args=(session.pk,))
        return HttpResponseRedirect(landing_url)

    def dispatch(self, request, *args, **kwargs):
        self.session_config_name = kwargs['session_config']
        return super(CreateDemoSession, self).dispatch(
            request, *args, **kwargs
        )

    def socket_url(self):
        return '/wait_for_demo_session/{}/'.format(self.session_config_name)


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
