from .settings import * # flake8: noqa


ROOT_URLCONF = 'tests.demo.urls'

CHANNEL_LAYERS['default']['ROUTING'] = 'tests.demo.routing.channel_routing'
