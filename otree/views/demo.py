import os

from otree import settings
from otree.session import SESSION_CONFIGS_DICT
from .cbv import AdminView


class DemoIndex(AdminView):
    url_pattern = '/demo'

    def vars_for_template(self):
        title = getattr(settings, 'DEMO_PAGE_TITLE', 'Demo')
        intro_html = getattr(settings, 'DEMO_PAGE_INTRO_HTML', '')
        session_info = []
        for session_config in SESSION_CONFIGS_DICT.values():
            session_info.append(
                {
                    'name': session_config['name'],
                    'display_name': session_config['display_name'],
                    'url': self.request.url_for(
                        'CreateDemoSession', config_name=session_config['name']
                    ),
                    'num_demo_participants': session_config['num_demo_participants'],
                }
            )

        if os.environ.get('OTREEHUB_PUB'):
            otreehub_app_name = os.environ.get('OTREEHUB_APP_NAME')
            otreehub_url = f'https://www.otreehub.com/projects/{otreehub_app_name}/'
        else:
            otreehub_url = ''

        return dict(
            session_info=session_info,
            title=title,
            intro_html=intro_html,
            is_debug=settings.DEBUG,
            otreehub_url=otreehub_url,
        )


class CreateDemoSession(AdminView):
    url_pattern = '/demo/{config_name}'

    def vars_for_template(self):
        return dict(config_name=self.request.path_params['config_name'])
