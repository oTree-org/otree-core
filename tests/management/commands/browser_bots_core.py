from django.core.management.base import BaseCommand
from django.core.management import call_command
import random

class Command(BaseCommand):

    def handle(self, *args, **options):
        config_names = [
            'skip_waitpage_lookahead',
            'skip_many',
            'group_by_arrival_time',
            # these ones take a long time, so put them last
            'misc_3p',
            'waitpage_set_field',
        ]

        for config_name in config_names:
            call_command('browser_bots', config_name)
