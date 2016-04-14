from django.core.management.base import BaseCommand
from honcho.manager import Manager
import os
import sys


class Command(BaseCommand):
    help = 'Will run celery and channels worker'

    def add_arguments(self, parser):
        pass

    def get_env(self, options):
        return os.environ.copy()

    def handle(self, *args, **options):
        manager = Manager()

        manager.add_process(
            'channels',
            'otree runchannelsworker',
            quiet=False,
            env=self.get_env(options))
        manager.add_process(
            'celery',
            'otree runceleryworker',
            quiet=False,
            env=self.get_env(options))

        manager.loop()
        sys.exit(manager.returncode)
