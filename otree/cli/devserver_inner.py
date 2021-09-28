from otree.checks import run_checks
from .base import BaseCommand
from .prodserver1of2 import get_addr_port, run_asgi_server
from ..database import save_sqlite_db, DB_FILE

print_function = print


ADVICE_DELETE_DB = f'ADVICE: Delete your database ({DB_FILE}).'


class Command(BaseCommand):
    def add_arguments(self, parser):

        # see log_action below; we only show logs of each request
        # if verbosity >= 1.
        # this still allows logger.info and logger.warning to be shown.
        # NOTE: if we change this back to 1, then need to update devserver
        # not to show traceback of errors.
        parser.set_defaults(verbosity=0)

        parser.add_argument(
            'addrport', nargs='?', help='Optional port number, or ipaddr:port'
        )

        parser.add_argument(
            '--is-reload', action='store_true', dest='is_reload', default=False,
        )

        parser.add_argument(
            '--is-zipserver', action='store_true', dest='is_zipserver', default=False,
        )

    def handle(self, *args, addrport, is_reload, is_zipserver, **options):
        self.is_zipserver = is_zipserver

        addr, port = get_addr_port(addrport, is_devserver=True)
        if not is_reload:
            run_checks()
            # 0.0.0.0 is not a regular IP address, so we can't tell the user
            # to open their browser to that address
            if addr == '127.0.0.1':
                addr_readable = 'localhost'
            elif addr == '0.0.0.0':
                addr_readable = '<ip_address>'
            else:
                addr_readable = addr
            print_function(
                (
                    f"Open your browser to http://{addr_readable}:{port}/\n"
                    "To quit the server, press Control+C.\n"
                )
            )

        try:
            run_asgi_server(addr, port, is_devserver=True)
        except KeyboardInterrupt:
            return
        finally:
            save_sqlite_db()
