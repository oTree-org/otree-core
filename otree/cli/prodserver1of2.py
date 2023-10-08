import logging
import os
import subprocess

from .base import BaseCommand

logger = logging.getLogger(__name__)

print_function = print


def run_asgi_server(addr, port, *, is_devserver=False):
    run_uvicorn(addr, port, is_devserver=is_devserver)


def run_uvicorn(addr, port, *, is_devserver):
    from uvicorn.main import Config, Server

    config = Config(
        'otree.asgi:app',
        host=addr,
        port=int(port),
        log_level='warning' if is_devserver else "info",
        log_config=None,  # oTree has its own logger
        # i suspect it was defaulting to something else
        workers=1,
        # websockets library handles disconnects & ping automatically,
        # so we can simplify code and also avoid H15 errors on heroku.
        ws='websockets',
        # ws='wsproto',
    )
    server = Server(config=config)
    server.run()


def get_addr_port(cli_addrport, is_devserver=False):
    default_addr = '127.0.0.1' if is_devserver else '0.0.0.0'
    default_port = os.environ.get('PORT') or 8000
    if not cli_addrport:
        return default_addr, default_port
    parts = cli_addrport.split(':')
    if len(parts) == 1:
        return default_addr, parts[0]
    return parts


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            'addrport', nargs='?', help='Optional port number, or ipaddr:port'
        )

    def handle(self, *args, addrport=None, verbosity=1, **kwargs):
        addr, port = get_addr_port(addrport)
        subprocess.Popen(
            ['otree', 'timeoutsubprocess', str(port)], env=os.environ.copy()
        )
        print_function('Running prodserver')
        run_asgi_server(addr, port)
