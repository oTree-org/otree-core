# -*- coding: utf-8 -*-

from django.conf import settings
from django.urls import reverse

import vanilla
from otree.session import SESSION_CONFIGS_DICT
from otree.common_internal import create_session_and_redirect


class DemoIndex(vanilla.TemplateView):

    template_name = 'otree/DemoIndex.html'

    url_pattern = r'^demo/$'

    def get_context_data(self, **kwargs):
        title = getattr(settings, 'DEMO_PAGE_TITLE', 'Demo')
        intro_html = (
            getattr(settings, 'DEMO_PAGE_INTRO_HTML', '') or
            getattr(settings, 'DEMO_PAGE_INTRO_TEXT', ''))
        context = super().get_context_data(**kwargs)

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
            'title': title,
            'intro_html': intro_html,
            'is_debug': settings.DEBUG,
        })
        return context


class CreateDemoSession(vanilla.GenericView):

    url_pattern = r"^demo/(?P<session_config>.+)/$"

    def dispatch(self, request, *args, **kwargs):
        session_config_name = kwargs['session_config']
        try:
            session_config = SESSION_CONFIGS_DICT[session_config_name]
        except KeyError:
            msg = 'Session config "{}" not found in settings.SESSION_CONFIGS.'
            raise ValueError(msg.format(session_config_name)) from None
        session_kwargs = {
            'is_demo': True,
            'session_config_name': session_config_name,
            'num_participants': session_config['num_demo_participants']
        }

        use_browser_bots = session_config.get('use_browser_bots', False)
        return create_session_and_redirect(
            session_kwargs, use_browser_bots=use_browser_bots)
