from django.core.management.base import BaseCommand
from django.core.management import call_command
import random

class Command(BaseCommand):

    def handle(self, *args, **options):
        config_names = [
            'saving',
            'skip_waitpage_lookahead',
            'skip_many',
            'gbat',
            # 2017-05-05: gbat_round1 was missing originally,
            # seems like it wasn't getting run at all. so i added it here
            'gbat_round1',
            'gbat_custom',
            # these ones take a long time, so put them last
            'misc_3p',
            'waitpage_set_field',
        ]

        for config_name in config_names:
            call_command('browser_bots', config_name)
