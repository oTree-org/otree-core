import os
import re
import daphne.cli
import logging
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
import otree

logger = logging.getLogger(__name__)

naiveip_re = re.compile(
    r"""^(?:
(?P<addr>
    (?P<ipv4>\d{1,3}(?:\.\d{1,3}){3}) |         # IPv4 address
    (?P<ipv6>\[[a-fA-F0-9:]+\]) |               # IPv6 address
    (?P<fqdn>[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*) # FQDN
):)?(?P<port>\d+)$""",
    re.X,
)

DEFAULT_PORT = "8000"
DEFAULT_ADDR = '0.0.0.0'


def get_addr_port(cli_addrport):
    if cli_addrport:
        m = re.match(naiveip_re, cli_addrport)
        if m is None:
            msg = (
                '"%s" is not a valid port number '
                'or address:port pair.' % cli_addrport
            )
            raise CommandError(msg)
        addr, _, _, _, port = m.groups()
    else:
        addr = None
        port = None

    addr = addr or DEFAULT_ADDR
    # Heroku uses PORT env var
    port = port or os.environ.get('PORT') or DEFAULT_PORT
    return addr, port


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            'addrport', nargs='?', help='Optional port number, or ipaddr:port'
        )

    def handle(self, *args, addrport=None, verbosity=1, **kwargs):
        addr, port = get_addr_port(addrport)

        # uvicorn isn't actually faster even with 3 processes
        # if os.environ.get('USE_UVICORN'):
        #     import uvicorn, sys
        #     uvicorn.run(
        #         'otree_startup.asgi:application',
        #         host=addr,
        #         port=port,
        #         log_level="info",
        #         workers=1 if sys.platform.startswith("win") else 3,
        #     )
        daphne.cli.CommandLineInterface().run(
            ['-b', addr, '-p', port, 'otree_startup.asgi:application']
        )
