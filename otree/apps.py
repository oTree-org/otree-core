import logging
import sys
import sqlite3

import django.db.utils
import colorama
from django.apps import AppConfig
from django.db.models import signals

from otree.common import ensure_superuser_exists
from otree.strict_templates import patch_template_silent_failures

try:
    from psycopg2.errors import UndefinedColumn, UndefinedTable
except ModuleNotFoundError:

    class UndefinedColumn(Exception):
        pass

    class UndefinedTable(Exception):
        pass


logger = logging.getLogger('otree')


def create_singleton_objects(sender, **kwargs):
    from otree.models_concrete import UndefinedFormModel

    for ModelClass in [UndefinedFormModel]:
        # if it doesn't already exist, create one.
        ModelClass.objects.get_or_create()


SQLITE_LOCKING_ADVICE = (
    'Locking is common with SQLite. '
    'When you run your study, you should use a database like PostgreSQL '
    'that is resistant to locking'
)


def patched_execute(self, sql, params=None):
    try:
        return self._execute_with_wrappers(
            sql, params, many=False, executor=self._execute
        )
    except Exception as exc:

        ExceptionClass = type(exc)
        tb = sys.exc_info()[2]
        # Django seems to reraise with new exceptions, so we need to look at the __cause__:
        # sqlite3.OperationalError -> django.db.utils.OperationalError
        # psycopg2.errors.UndefinedColumn -> django.db.utils.ProgrammingError
        CauseClass = type(exc.__cause__)

        if CauseClass == sqlite3.OperationalError and 'locked' in str(exc):
            raise ExceptionClass(f'{exc} - {SQLITE_LOCKING_ADVICE}.').with_traceback(
                tb
            ) from None

        # this will only work on postgres, but if they are using sqlite they should be using
        # devserver anyway.
        if CauseClass in (UndefinedColumn, UndefinedTable):
            msg = f'{exc} - try resetting the database.'
            raise ExceptionClass(msg).with_traceback(tb) from None
        raise


def monkey_patch_db_cursor():
    '''Monkey-patch the DB cursor, to catch ProgrammingError and
    OperationalError. The alternative is to use middleware, but (1)
    that doesn't catch errors raised outside of views, like channels consumers
    and the task queue, and (2) it's not as specific, because there are
    OperationalErrors that come from different parts of the app that are
    unrelated to resetdb. This is the most targeted location.
    '''

    from django.db.backends import utils

    utils.CursorWrapper.execute = patched_execute


def setup_create_default_superuser():
    signals.post_migrate.connect(
        ensure_superuser_exists, dispatch_uid='otree.create_superuser'
    )


def setup_create_singleton_objects():
    signals.post_migrate.connect(
        create_singleton_objects, dispatch_uid='create_singletons'
    )


class OtreeConfig(AppConfig):
    name = 'otree'
    label = 'otree'
    verbose_name = "oTree"

    def ready(self):
        setup_create_singleton_objects()
        setup_create_default_superuser()
        monkey_patch_db_cursor()

        colorama.init(autoreset=True)

        import otree.checks

        otree.checks.register_system_checks()
        patch_template_silent_failures()

        # initialize browser bot worker in process memory
        import otree.bots.browser

        otree.bots.browser.browser_bot_worker = otree.bots.browser.BotWorker()
