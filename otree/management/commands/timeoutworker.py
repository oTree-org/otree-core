#!/usr/bin/env python
import os
import sys

from honcho.manager import Manager
from channels.log import setup_logger
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run timeoutworker (plus botworker).'

    def add_arguments(self, parser):
        BaseCommand.add_arguments(self, parser)

    def get_env(self, options):
        return os.environ.copy()

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.logger = setup_logger('django.channels', self.verbosity)
        manager = self.get_honcho_manager(options)
        manager.loop()
        sys.exit(manager.returncode)

    def get_honcho_manager(self, options):

        manager = Manager()

        # if I change these, I need to modify the ServerCheck also
        manager.add_process(
            'botworker',
            'otree botworker',
            quiet=False,
            env=os.environ.copy()
        )
        manager.add_process(
            'timeoutworkeronly',
            'otree timeoutworkeronly',
            quiet=False,
            env=os.environ.copy()
        )

        return manager
