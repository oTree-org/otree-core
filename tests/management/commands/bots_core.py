from django.core.management.base import BaseCommand
from django.core.management import call_command
import random

class Command(BaseCommand):

    def handle(self, *args, **options):
        config_names = [
            'saving',
        ]

        for config_name in config_names:
            call_command('test', config_name)
