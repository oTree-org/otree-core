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
from otree.common_internal import channels_create_session_group_name
from six.moves import range
import uuid

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


class CreateDemoSession(vanilla.GenericView):

    @classmethod
    def url_pattern(cls):
        return r"^demo/(?P<session_config>.+)/$"

    @classmethod
    def url_name(cls):
        return 'create_demo_session'

    def dispatch(self, request, *args, **kwargs):
        session_config_name = kwargs['session_config']
        try:
            session_config = SESSION_CONFIGS_DICT[session_config_name]
        except KeyError:
            msg = (
                "Session config '{}' not found"
            ).format(session_config_name)
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
                session_config_name,
                num_participants,
                session_lcm
            )
            raise Http404(msg)

        pre_create_id = uuid.uuid4().hex
        kwargs = {
            'special_category': constants.session_special_category_demo,
            'session_config_name': session_config_name,
            '_pre_create_id': pre_create_id,
        }

        channels_group_name = channels_create_session_group_name(
            pre_create_id)
        channels.Channel('otree.create_session').send({
            'kwargs': kwargs,
            'channels_group_name': channels_group_name
        })

        wait_for_session_url = reverse(
            'wait_for_session', args=(pre_create_id,)
        )
        return HttpResponseRedirect(wait_for_session_url)


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
