import os
import re
import sys
import logging

import honcho.manager

from channels.log import setup_logger

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
import otree

logger = logging.getLogger(__name__)

naiveip_re = re.compile(r"""^(?:
(?P<addr>
    (?P<ipv4>\d{1,3}(?:\.\d{1,3}){3}) |         # IPv4 address
    (?P<ipv6>\[[a-fA-F0-9:]+\]) |               # IPv6 address
    (?P<fqdn>[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*) # FQDN
):)?(?P<port>\d+)$""", re.X)

DEFAULT_PORT = "8000"
DEFAULT_ADDR = '0.0.0.0'
NUM_WORKERS = 3

# made this simple class to reduce code duplication,
# and to make testing easier (I didn't know how to check that it was called
# with os.environ.copy(), especially if we patch os.environ)
class OTreeHonchoManager(honcho.manager.Manager):
    def add_otree_process(self, name, cmd):
        self.add_process(name, cmd, env=os.environ.copy(), quiet=False)

def twisted_ssl_file_path(filename):
    otree_dir = os.path.dirname(otree.__file__)
    pth = os.path.join(otree_dir, 'certs', filename)
    return pth.replace('\\', '/').replace(':', '\\:')

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
        ahelp = (
            'Run an SSL server directly in Daphne. '
            'You must put a server.key and server.crt in your project root.'
        )
        parser.add_argument(
            '--dev-https', action='store_true', dest='dev_https', default=False,
            help=ahelp)

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.logger = setup_logger('django.channels', self.verbosity)
        self.honcho = OTreeHonchoManager()
        self.setup_honcho(options)
        self.honcho.loop()
        sys.exit(self.honcho.returncode)

    def setup_honcho(self, options):

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

        daphne_cmd = 'daphne otree.asgi:channel_layer'
        if options['dev_https']:
            # don't need to check for existence of key/cert files, because Twisted will complain
            # if they are missing
            daphne_cmd += ' -e ssl:{}:privateKey={}:certKey={}:interface={}'.format(
                port,
                twisted_ssl_file_path('development.crt'),
                twisted_ssl_file_path('development.key'),
                addr)
            logger.info('Starting daphne HTTPS server on {}:{} (development/testing only)'.format(addr, port))
        else:
            daphne_cmd += ' -b {} -p {}'.format(addr, port)
            logger.info('Starting daphne server on {}:{}'.format(addr, port))

        honcho = self.honcho
        honcho.add_otree_process('daphne', daphne_cmd)
        for i in range(NUM_WORKERS):
            honcho.add_otree_process(
                'worker{}'.format(i),
                'otree runworker')
