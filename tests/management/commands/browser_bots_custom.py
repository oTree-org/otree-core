from django.core.management.base import BaseCommand
from django.core.management import call_command
import random

class Command(BaseCommand):

    def handle(self, *args, **options):
        config_names = ['group_by_arrival_time_round1'] * 10 + ['group_by_arrival_time_custom'] * 10
        for config_name in config_names:
            call_command('browser_bots', config_name)
