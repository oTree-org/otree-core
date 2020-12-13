import importlib
import sys
import time
import traceback
from pathlib import Path
import signal
from contextlib import contextmanager

from otree.common import dump_db, dump_db_and_exit, load_db

import termcolor
from django.apps import apps
from django.conf import settings
from django.core.management import call_command, BaseCommand

import otree_startup
from otree import __version__ as CURRENT_VERSION
from otree.common import dump_db, load_db
from .prodserver1of2 import get_addr_port, run_asgi_server

TMP_MIGRATIONS_DIR = Path('__temp_migrations')
VERSION_FILE = TMP_MIGRATIONS_DIR.joinpath('otree-version.txt')

ADVICE_DELETE_TMP = (
    "ADVICE: Try deleting the folder {}. If that doesn't work, "
    "look for the error in your models.py."
).format(TMP_MIGRATIONS_DIR)

# this happens when I add a non-nullable field to oTree-core
# (includes renaming a non-nullable field)
ADVICE_FIX_NOT_NULL_FIELD = (
    'You may have added a non-nullable field without a default. '
    'This typically happens when importing model fields from django instead of otree.'
)

PRINT_DETAILS_VERBOSITY_LEVEL = 1

ADVICE_PRINT_DETAILS = (
    '(For technical details about this error, run "otree devserver --verbosity=1")'
).format(PRINT_DETAILS_VERBOSITY_LEVEL)


ADVICE_DELETE_DB = (
    'ADVICE: Stop the server, '
    'then delete the file db.sqlite3 in your project folder.'
)

# They should start fresh so that:
# (1) performance refresh
# (2) don't have to worry about old references to things that were removed from otree-core.
MSG_OTREE_UPDATE_DELETE_DB = (
    'oTree has been updated. Please delete your database (usually "db.sqlite3") '
    f'and the folder "{TMP_MIGRATIONS_DIR}".'
)


@contextmanager
def patch_stdout():
    '''better than importing unittest.mock just to use this'''
    orig = sys.stdout.write
    sys.stdout.write = lambda s: None
    try:
        yield
    finally:
        sys.stdout.write = orig


class Command(BaseCommand):
    # Validation is called explicitly on first load, see below.
    requires_system_checks = False

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
        self.verbosity = options.get("verbosity", 1)
        self.is_zipserver = is_zipserver

        if not settings.DEBUG:
            # this tends to cause confusion. people don't know why they get server 500 error,
            # and it's worse with zipserver, where it is not possible to run collectstatic.
            sys.exit(
                'Error: devserver & zipserver cannot be used in production mode. '
                'Ensure that your settings.py does not contain a DEBUG setting, '
                'and that the OTREE_PRODUCTION env var is not set.'
            )

        if not is_reload:
            try:
                # don't suppress output. it's good to know that check is
                # not failing silently or not being run.
                # also, intercepting stdout doesn't even seem to work here.
                self.check(display_num_errors=True)
            except Exception as exc:
                otree_startup.print_colored_traceback_and_exit(exc)

            # better to do this here, because:
            # (1) it's redundant to do it on every reload
            # (2) we can exit if we run this before the autoreloader is started
            if VERSION_FILE.exists() and VERSION_FILE.read_text() != CURRENT_VERSION:
                # - Don't delete the DB, because it might have important data
                # - Don't delete __temp_migrations, because then we erase the knowledge that
                # oTree was updated. If the user starts the server at a later time, we can't remind them
                # that they needed to delete the DB. So, the two things must be deleted together.
                self.stdout.write(MSG_OTREE_UPDATE_DELETE_DB)
                sys.exit(0)
            TMP_MIGRATIONS_DIR.mkdir(exist_ok=True)
            VERSION_FILE.write_text(CURRENT_VERSION)
            TMP_MIGRATIONS_DIR.joinpath('__init__.py').touch(exist_ok=True)
            # python docs say: invalidate_cache must be called after creating new modules
            # i suspect invalidate_cache is needed to avoid this issue:
            # https://groups.google.com/d/msg/otree/d3fOpKCgLWo/-TSiZHy5CAAJ
            # because it only happened on mac and was sporadic like a race condition
            # seems to have no impact on perf
            importlib.invalidate_caches()

        self.makemigrations_and_migrate()

        addr, port = get_addr_port(addrport, is_devserver=True)
        if not is_reload:
            # 0.0.0.0 is not a regular IP address, so we can't tell the user
            # to open their browser to that address
            if addr == '127.0.0.1':
                addr_readable = 'localhost'
            elif addr == '0.0.0.0':
                addr_readable = '<ip_address>'
            else:
                addr_readable = addr
            self.stdout.write(
                (
                    f"Open your browser to http://{addr_readable}:{port}/\n"
                    "To quit the server, press Control+C.\n"
                )
            )

        try:
            run_asgi_server(addr, port, is_devserver=True)
            dump_db()  # for hypercorn 0.11 with Ctrl+C
        except KeyboardInterrupt:
            return
        except SystemExit as exc:
            dump_db()
            raise

    def makemigrations_and_migrate(self):

        # only get apps with models, otherwise migrate will raise an error
        # when it tries to migrate that app but no migrations dir was created
        app_labels = set(model._meta.app_config.label for model in apps.get_models())

        migrations_modules = {
            app_label: '{}.{}'.format(TMP_MIGRATIONS_DIR, app_label)
            for app_label in app_labels
        }
        settings.MIGRATION_MODULES = migrations_modules
        start = time.time()

        try:
            # makemigrations rarely sends any interesting info to stdout.
            # if there is an error, it will go to stderr,
            # or raise CommandError.
            # if someone needs to see the details of makemigrations,
            # they can do "otree makemigrations".
            with patch_stdout():
                call_command('makemigrations', '--noinput', *migrations_modules.keys())

        except SystemExit as exc:
            # SystemExit will be raised if NonInteractiveMigrationQuestioner
            # cannot decide what to do automatically.
            # SystemExit does not inherit from Exception,
            # so we need to catch it explicitly.
            # without this, the process will just exit and the autoreloader
            # will hang.
            self.print_error_and_exit(ADVICE_FIX_NOT_NULL_FIELD)
        except Exception as exc:
            self.print_error_and_exit(ADVICE_DELETE_TMP)

        # migrate imports some modules that were created on the fly,
        # so according to the docs for import_module, we need to call
        # invalidate_cache.
        # the following line is necessary to avoid a crash I experienced
        # on Mac, because makemigrations tries some imports which cause ImportErrors,
        # messes up the cache on some systems.
        importlib.invalidate_caches()

        # should I instead connect to connection_created signal?
        # but this seems better because we know exactly where it happens,
        # and can guarantee we won't subscribe after the signal was already sent.

        load_db()
        # this handles:
        # (1) keyboardinterrupt
        # (2) external interrupts
        # so, it's probably more complete than just having a KeyboardInterrupt handler
        # especially if the exception occurs outside the try/except
        signal.signal(signal.SIGINT, dump_db_and_exit)

        try:
            # see above comment about makemigrations and capturing stdout.
            # it applies to migrate command also.
            with patch_stdout():
                # call_command does not add much overhead (0.1 seconds typical)
                call_command('migrate', '--noinput')

        except Exception as exc:
            # it seems there are different exceptions all named
            # OperationalError (django.db.OperationalError,
            # sqlite.OperationalError, mysql....)
            # so, simplest to use the string name

            if type(exc).__name__ in (
                'OperationalError',
                'ProgrammingError',
                'InconsistentMigrationHistory',
            ):
                self.print_error_and_exit(ADVICE_DELETE_DB)
            else:
                raise

        total_time = round(time.time() - start, 1)
        if total_time > 5:
            self.stdout.write('makemigrations & migrate ran in {}s'.format(total_time))

    def print_error_and_exit(self, advice):
        '''this won't actually exit because we can't kill the autoreload process'''
        self.stdout.write('\n')
        is_verbose = self.verbosity >= PRINT_DETAILS_VERBOSITY_LEVEL
        show_error_details = is_verbose or self.is_zipserver
        if show_error_details:
            traceback.print_exc()
        else:
            self.stdout.write('An error occurred.')
        if self.is_zipserver:
            self.stdout.write('Please report to chris@otree.org.')
        else:
            termcolor.cprint(advice, 'white', 'on_red')
        if not show_error_details:
            self.stdout.write(ADVICE_PRINT_DETAILS)
        sys.exit(0)
