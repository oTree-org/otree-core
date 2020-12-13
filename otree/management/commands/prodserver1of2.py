import asyncio
import logging
import os
from otree.common import dump_db
from django.core.management.base import BaseCommand
from otree_startup.asgi import application
import sys
import subprocess

logger = logging.getLogger(__name__)


def run_asgi_server(addr, port, *, is_devserver=False):
    run_hypercorn(addr, port, is_devserver=is_devserver)


def run_hypercorn(addr, port, *, is_devserver=False):

    from hypercorn_otree import Config as HypercornConfig
    from hypercorn_otree.asyncio import serve

    config = HypercornConfig()
    config.bind = f'{addr}:{port}'
    if is_devserver:
        # We want to hide "Running on 127.0.0.1 over https (CTRL + C to quit)")
        # and show our localhost message instead.
        # hypercorn doesn't seem to log anything important to .info anyway.
        config.loglevel = 'warning'
    else:
        config.accesslog = '-'  # go to stdout
        # for some reason access_log_format works with hypercorn 0.9.2 but not 0.11
        config.access_log_format = '%(h)s %(S)s "%(r)s" %(s)s'

    loop = asyncio.get_event_loop()

    # i have alternated between using shutdown_trigger and sys.exit().
    # originally when i was doing sys.exit() in the TerminateServer view,
    # it kept printing out the SystemExit traceback but not actually terminating the server
    # but now it works (not sure what changed).
    # and shutdown_trigger sometimes caused the app to hang.
    loop.run_until_complete(serve(application, config))


def run_uvicorn(addr, port, *, is_devserver):
    from uvicorn.main import Config, ChangeReload, Multiprocess, Server

    class OTreeUvicornServer(Server):
        def __init__(self, config, *, is_devserver):
            self.is_devserver = is_devserver
            super().__init__(config)

        def handle_exit(self, sig, frame):
            if self.is_devserver:
                dump_db()
            return super().handle_exit(sig, frame)

    '''modified uvicorn.main.run to use our custom subclasses'''

    config = Config(
        'otree_startup.asgi:application',
        host=addr,
        port=int(port),
        log_level='warning' if is_devserver else "info",
        # i suspect it was defaulting to something else
        workers=1,
        # on heroku, need websockets to avoid H15, but locally want to avoid
        # https://github.com/encode/uvicorn/issues/757
        ws='wsproto',
    )
    server = OTreeUvicornServer(config=config, is_devserver=is_devserver)

    assert config.workers == 1
    if config.should_reload:
        sock = config.bind_socket()
        supervisor = ChangeReload(config, target=server.run, sockets=[sock])
        supervisor.run()
    else:
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
        subprocess.Popen([sys.executable, 'manage.py', 'timeoutsubprocess', str(port)])
        run_asgi_server(addr, port)
