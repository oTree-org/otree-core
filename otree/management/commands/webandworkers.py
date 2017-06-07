#!/usr/bin/env python
import os
import re
import sys

from honcho.manager import Manager

from channels.log import setup_logger

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

naiveip_re = re.compile(r"""^(?:
(?P<addr>
    (?P<ipv4>\d{1,3}(?:\.\d{1,3}){3}) |         # IPv4 address
    (?P<ipv6>\[[a-fA-F0-9:]+\]) |               # IPv6 address
    (?P<fqdn>[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*) # FQDN
):)?(?P<port>\d+)$""", re.X)

DEFAULT_PORT = "8000"
DEFAULT_ADDR = '0.0.0.0'


class Command(BaseCommand):
    help = 'Run otree web services for the production environment.'

    def add_arguments(self, parser):
        BaseCommand.add_arguments(self, parser)

        parser.add_argument('addrport', nargs='?',
            help='Optional port number, or ipaddr:port')

        # The below flags are for legacy compat.
        # 2017-06-08 added addrport positional argument,
        # because:
        # - more consistent with runserver.
        # - don't have to remember the name of the flags (is it --bind or --addr etc)
        # - quicker to type
        # - we don't need positional args for anything else

        parser.add_argument(
            '--addr', action='store', type=str, dest='addr', default=None,
            help='The host/address to bind to (default: {})'.format(DEFAULT_ADDR))

        ahelp = (
            'Port number to listen on. Defaults to the environment variable '
            '$PORT (if defined), or {}.'.format(DEFAULT_PORT)
        )
        parser.add_argument(
            '--port', action='store', type=int, dest='port', default=None,
            help=ahelp)

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.logger = setup_logger('django.channels', self.verbosity)
        manager = self.get_honcho_manager(options)
        manager.loop()
        sys.exit(manager.returncode)

    def get_honcho_manager(self, options):

        if options.get('addrport'):
            m = re.match(naiveip_re, options['addrport'])
            if m is None:
                raise CommandError('"%s" is not a valid port number '
                                   'or address:port pair.' % options['addrport'])
            addr, _, _, _, port = m.groups()
        else:
            addr = options['addr']
            port = options['port']
        addr = addr or DEFAULT_ADDR
        port = port or os.environ.get('PORT') or DEFAULT_PORT

        manager = Manager()

        daphne_cmd = 'daphne otree.asgi:channel_layer -b {} -p {}'.format(
            addr,
            port
        )

        print('Starting daphne server on {}:{}'.format(addr, port))

        manager.add_process('daphne', daphne_cmd, env=os.environ.copy())
        for i in range(3):
            manager.add_process(
                'worker{}'.format(i),
                'otree runworker',
                env=os.environ.copy())

        return manager
