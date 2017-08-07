from django.core.management.base import BaseCommand
from django.core.management import call_command
import random

class Command(BaseCommand):

    def handle(self, *args, **options):
        config_names = [
            'saving',
            'skip_waitpage_lookahead',
            'skip_many',
            'group_by_arrival_time',
            # 2017-05-05: group_by_arrival_time_round1 was missing originally,
            # seems like it wasn't getting run at all. so i added it here
            'group_by_arrival_time_round1',
            'group_by_arrival_time_custom',
            # these ones take a long time, so put them last
            'misc_3p',
            'waitpage_set_field',
        ]

        for config_name in config_names:
            call_command('browser_bots', config_name)
