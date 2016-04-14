#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

from django.core.management.base import BaseCommand
from honcho.manager import Manager


class Command(BaseCommand):
    help = 'Run otree development server.'

    default_port = 8000

    def add_arguments(self, parser):
        ahelp = (
            'By default we will collect all static files into the directory '
            'configured in your settings. Disable it with this switch if you '
            'want to do it manually.')
        parser.add_argument(
            '--no-collectstatic', action='store_false', dest='collectstatic',
            default=True, help=ahelp)

        ahelp = (
            'The port that the http server should run on. It defaults to '
            '8000. This value can be set by the environment variable $PORT.')
        parser.add_argument(
            '--port', action='store', type=int, dest='port', default=None,
            help=ahelp)

    def get_port(self, suggested_port):
        if suggested_port is None:
            suggested_port = os.environ.get('PORT', None)
        try:
            return int(suggested_port)
        except (ValueError, TypeError):
            return self.default_port

    def get_env(self, options):
        port = self.get_port(options['port'])
        env = os.environ.copy()
        env.setdefault('OTREE_DEVELOP', '1')
        env.setdefault('OTREE_DEBUG', '1')
        env.setdefault('PORT', str(port))
        return env

    def handle(self, *args, **options):
        manager = Manager()

        manager.add_process(
            'web',
            'otree runweb --reload',
            quiet=False,
            env=self.get_env(options))
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
