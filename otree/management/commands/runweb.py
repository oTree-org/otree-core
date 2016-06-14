#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import otree
import re
import sys

from django.conf import settings
from channels import DEFAULT_CHANNEL_LAYER, channel_layers
from channels.handler import ViewConsumer
from channels.log import setup_logger
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
import django.core.management.commands.runserver

from twisted.internet import reactor, ssl
from daphne.server import Server
from daphne.http_protocol import HTTPFactory


class SecureServer(Server):
    def run(self):
        """
        A version of daphne Server.run() which supports SSL
        """
        self.factory = HTTPFactory(
            self.channel_layer,
            self.action_logger,
            timeout=self.http_timeout,
            websocket_timeout=self.websocket_timeout,
            ping_interval=self.ping_interval,
            ws_protocols=self.ws_protocols,
        )
        # Hardcoded for now
        ssl_context = ssl.DefaultOpenSSLContextFactory(
            ssl_file('development.key'),
            ssl_file('development.crt'),
        )
        reactor.listenSSL(self.port, self.factory, ssl_context)

        reactor.callLater(0, self.backend_reader)
        reactor.callLater(2, self.timeout_checker)
        reactor.run(installSignalHandlers=self.signal_handlers)


def ssl_file(filename):
    otree_dir = os.path.dirname(otree.__file__)
    return os.path.join(otree_dir, 'certs', filename)



RunserverCommand = django.core.management.commands.runserver.Command


naiveip_re = re.compile(r"""^
(?P<addr>
    (?P<ipv4>\d{1,3}(?:\.\d{1,3}){3}) |         # IPv4 address
    (?P<ipv6>\[[a-fA-F0-9:]+\]) |               # IPv6 address
    (?P<fqdn>[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*) # FQDN
)$""", re.X)


class Command(RunserverCommand):
    help = 'Run otree web services for the production environment.'

    default_port = 5000

    def add_arguments(self, parser):
        BaseCommand.add_arguments(self, parser)

        ahelp = ('TODO')
        parser.add_argument(
            '--reload', action='store_true', dest='use_reloader',
            default=False, help=ahelp)

        ahelp = (
            'The port that the http server should run on. It defaults to '
            '5000. This value can be set by the environment variable $PORT.')
        parser.add_argument(
            '--port', action='store', type=int, dest='port', default=None,
            help=ahelp)
        parser.add_argument(
            '--addr', action='store', type=str, dest='addr', default='0.0.0.0',
            help=ahelp)

    def get_port(self, suggested_port):
        if suggested_port is None:
            suggested_port = os.environ.get('PORT', None)
        try:
            return int(suggested_port)
        except (ValueError, TypeError):
            return self.default_port

    def get_addr(self, suggested_addr):
        if not naiveip_re.match(suggested_addr):
            raise CommandError('--addr option must be a valid IP address.')
        return suggested_addr

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.logger = setup_logger('django.channels', self.verbosity)
        return super(Command, self).handle(*args, **options)

    def inner_run(self, *args, **options):
        # Check a handler is registered for http reqs; if not, add default one
        self.channel_layer = channel_layers[DEFAULT_CHANNEL_LAYER]
        self.channel_layer.router.check_default(
            http_consumer=ViewConsumer(),
        )

        self.addr = self.get_addr(options['addr'])
        self.port = self.get_port(options['port'])

        # Run checks
        self.stdout.write("Performing system checks...\n\n")
        self.check(display_num_errors=True)
        self.check_migrations()

        # Print helpful text
        quit_command = 'CTRL-BREAK' if sys.platform == 'win32' else 'CONTROL-C'
        self.stdout.write((
            "\n"
            "otree-core version %(otree_version)s, "
            "Django version %(django_version)s, "
            "using settings %(settings)r\n"
            "Starting web server at %(proto)s://%(addr)s:%(port)s/\n"
            # "Channel layer %(layer)s\n"
            "Quit the server with %(quit_command)s.\n"
        ) % {
            "django_version": self.get_version(),
            "otree_version": otree.__version__,
            "settings": settings.SETTINGS_MODULE,
            "proto": 'https' if os.environ.get('HTTPS') else 'http',
            "addr": '[%s]' % self.addr if self._raw_ipv6 else self.addr,
            "port": self.port,
            "quit_command": quit_command,
            "layer": self.channel_layer,
        })
        self.stdout.flush()

        # Launch server in 'main' thread. Signals are disabled as it's still
        # actually a subthread under the autoreloader.
        self.logger.debug("Daphne running, listening on %s:%s",
                          self.addr, self.port)

        try:
            server_cls = SecureServer if os.environ.get('HTTPS') else Server
            server = server_cls(
                channel_layer=self.channel_layer,
                host=self.addr,
                port=int(self.port),
                signal_handlers=not options['use_reloader'],
            ).run()
            self.logger.debug("Daphne exited")
        except KeyboardInterrupt:
            shutdown_message = options.get('shutdown_message', '')
            if shutdown_message:
                self.stdout.write(shutdown_message)
            return
