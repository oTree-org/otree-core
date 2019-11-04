import importlib
import logging
import os
import os.path
import shutil
import sys
import time
import traceback
from pathlib import Path
from unittest.mock import patch

import termcolor
from channels.management.commands import runserver
from daphne.endpoints import build_endpoint_description_strings
from django.apps import apps
from django.conf import settings
from django.core.management import call_command

import otree.bots.browser
import otree.common
import otree_startup
from otree import __version__ as CURRENT_VERSION

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

db_engine = settings.DATABASES['default']['ENGINE'].lower()

if otree.common.is_sqlite():
    ADVICE_DELETE_DB = (
        'ADVICE: Stop the server, '
        'then delete the file db.sqlite3 in your project folder, '
        'then run "otree devserver", not "otree resetdb".'
    )
else:
    if 'postgres' in db_engine:
        db_engine = 'PostgreSQL'
    elif 'mysql' in db_engine:
        db_engine = 'MySQL'

    ADVICE_DELETE_DB = (
        'ADVICE: Delete (drop) your {} database, then create a new empty one '
        'with the same name. "otree devserver" cannot be used on a database '
        'that was generated with "otree resetdb". You should either use one '
        'command or the other.'
    ).format(db_engine)

# They should start fresh so that:
# (1) performance refresh
# (2) don't have to worry about old references to things that were removed from otree-core.
MSG_OTREE_UPDATE_DELETE_DB = (
    'oTree has been updated. Please delete your database (usually "db.sqlite3") '
    f'and the folder "{TMP_MIGRATIONS_DIR}".'
)


class Command(runserver.Command):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        # see log_action below; we only show logs of each request
        # if verbosity >= 1.
        # this still allows logger.info and logger.warning to be shown.
        # NOTE: if we change this back to 1, then need to update devserver
        # not to show traceback of errors.
        parser.set_defaults(verbosity=0)

        parser.add_argument(
            '--inside-runzip', action='store_true', dest='inside_runzip', default=False
        )

    def handle(self, *args, **options):
        self.verbosity = options.get("verbosity", 1)
        from otree.common import release_any_stale_locks

        release_any_stale_locks()

        # for performance,
        # only run checks when the server starts, not when it reloads
        # (RUN_MAIN is set by Django autoreloader).
        if not os.environ.get('RUN_MAIN'):

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
            if TMP_MIGRATIONS_DIR.exists() and (
                not VERSION_FILE.exists() or VERSION_FILE.read_text() != CURRENT_VERSION
            ):
                # - Don't delete the DB, because it might have important data
                # - Don't delete __temp_migrations, because then we erase the knowledge that
                # oTree was updated. If the user starts the server at a later time, we can't remind them
                # that they needed to delete the DB. So, the two things must be deleted together.
                self.stdout.write(MSG_OTREE_UPDATE_DELETE_DB)
                sys.exit(0)
            TMP_MIGRATIONS_DIR.mkdir(exist_ok=True)
            VERSION_FILE.write_text(CURRENT_VERSION)
            TMP_MIGRATIONS_DIR.joinpath('__init__.py').touch(exist_ok=True)

        super().handle(*args, **options)

    def inner_run(self, *args, inside_runzip, **options):
        '''
        inner_run does not get run twice with runserver, unlike .handle()
        '''

        self.inside_runzip = inside_runzip
        self.makemigrations_and_migrate()

        # initialize browser bot worker in process memory
        otree.bots.browser.browser_bot_worker = otree.bots.browser.Worker()

        # silence the lines like:
        # 2018-01-10 18:51:18,092 - INFO - worker - Listening on channels
        # http.request, otree.create_session, websocket.connect,
        # websocket.disconnect, websocket.receive
        daphne_logger = logging.getLogger('django.channels')
        original_log_level = daphne_logger.level
        daphne_logger.level = logging.WARNING

        endpoints = build_endpoint_description_strings(host=self.addr, port=self.port)
        application = self.get_application(options)

        # silence the lines like:
        # INFO HTTP/2 support not enabled (install the http2 and tls Twisted extras)
        # INFO Configuring endpoint tcp:port=8000:interface=127.0.0.1
        # INFO Listening on TCP address 127.0.0.1:8000
        logging.getLogger('daphne.server').level = logging.WARNING

        # I removed the IPV6 stuff here because its not commonly used yet
        addr = self.addr
        # 0.0.0.0 is not a regular IP address, so we can't tell the user
        # to open their browser to that address
        if addr == '127.0.0.1':
            addr = 'localhost'
        elif addr == '0.0.0.0':
            addr = '<ip_address>'
        self.stdout.write(
            (
                f"Open your browser to http://{addr}:{self.port}/\n"
                "To quit the server, press Control+C.\n"
            )
        )

        try:
            self.server_cls(
                application=application,
                endpoints=endpoints,
                signal_handlers=not options["use_reloader"],
                action_logger=self.log_action,
                http_timeout=self.http_timeout,
                root_path=getattr(settings, "FORCE_SCRIPT_NAME", "") or "",
                websocket_handshake_timeout=self.websocket_handshake_timeout,
            ).run()
            daphne_logger.debug("Daphne exited")
        except KeyboardInterrupt:
            shutdown_message = options.get("shutdown_message", "")
            if shutdown_message:
                self.stdout.write(shutdown_message)
            return

    def makemigrations_and_migrate(self):

        # only get apps with labels, otherwise migrate will raise an error
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
            # if there is an error, it will go to stdout,
            # or raise CommandError.
            # if someone needs to see the details of makemigrations,
            # they can do "otree makemigrations".
            with patch('sys.stdout.write'):
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

        try:
            # see above comment about makemigrations and capturing stdout.
            # it applies to migrate command also.
            with patch('sys.stdout.write'):
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
        show_error_details = is_verbose or self.inside_runzip
        if show_error_details:
            traceback.print_exc()
        else:
            self.stdout.write('An error occurred.')
        if not self.inside_runzip:
            termcolor.cprint(advice, 'white', 'on_red')
        if not show_error_details:
            self.stdout.write(ADVICE_PRINT_DETAILS)
        sys.exit(0)

    def log_action(self, protocol, action, details):
        '''
        Override log_action method.
        Need this until https://github.com/django/channels/issues/612
        is fixed.
        maybe for some minimal output use this?
            self.stderr.write('.', ending='')
        so that you can see that the server is running
        (useful if you are accidentally running multiple servers)

        idea: maybe only show details if it's a 4xx or 5xx.

        '''
        if self.verbosity >= 1:
            super().log_action(protocol, action, details)

    inside_runzip = False
