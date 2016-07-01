# -*- coding: utf-8 -*-

import uuid

from django.conf import settings
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse

import vanilla

import channels

import otree.constants_internal as constants
from otree.session import SESSION_CONFIGS_DICT
from otree.common_internal import channels_create_session_group_name

# if it's debug mode, we should always generate a new session
# because a bug might have been fixed
# in production, we optimize for UX and quick loading
MAX_SESSIONS_TO_CREATE = 1 if settings.DEBUG else 3


class DemoIndex(vanilla.TemplateView):

    template_name = 'otree/demo/index.html'

    url_pattern = r'^demo/$'

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
                        'CreateDemoSession', args=(session_config['name'],)
                    ),
                    'num_demo_participants': session_config[
                        'num_demo_participants'
                    ]
                }
            )

        context.update({
            'session_info': session_info,
            'intro_text': intro_text,
            'is_debug': settings.DEBUG,
        })
        return context


class CreateDemoSession(vanilla.GenericView):

    url_pattern = r"^demo/(?P<session_config>.+)/$"

    def dispatch(self, request, *args, **kwargs):
        session_config_name = kwargs['session_config']
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
            'WaitUntilSessionCreated', args=(pre_create_id,)
        )
        return HttpResponseRedirect(wait_for_session_url)
