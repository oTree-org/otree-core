from channels.management.commands.runserver import Command as BaseCommand
import otree.common_internal
from django.conf import settings

class Command(BaseCommand):

    def handle(self, *args, **options):
        # use in-memory.
        # this is the simplest way to patch runserver to use in-memory,
        # while still using Redis in production
        settings.CHANNEL_LAYERS['default'] = settings.CHANNEL_LAYERS['inmemory']

        # so we know not to use Huey
        otree.common_internal.USE_REDIS = False
        super(Command, self).handle(*args, **options)
