#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connections

import six
import mock
from django.db.migrations.loader import MigrationLoader

# =============================================================================
# LOGGER
# =============================================================================

logger = logging.getLogger('otree')


# =============================================================================
# CONSTANTS
# =============================================================================

RESETDB_DROP_TABLES = {
    "django.db.backends.sqlite3": 'DROP TABLE {table};',
    "django.db.backends.oracle": 'DROP TABLE {table} CASCADE CONSTRAINTS;',
    "django.db.backends.postgresql": 'DROP TABLE {table} CASCADE;',
    "django.db.backends.mysql": (
        'SET FOREIGN_KEY_CHECKS = 0;'
        'DROP TABLE {table} CASCADE;'
        'SET FOREIGN_KEY_CHECKS = 1;'),

    # DJANGO < 1.9
    "django.db.backends.postgresql_psycopg2": 'DROP TABLE {table} CASCADE;',
}


CUSTOM_RESETDB_DROP_TABLES = getattr(
    settings, "RESETDB_DROP_TABLES", None) or {}


# =============================================================================
# COMMND
# =============================================================================

class Command(BaseCommand):
    help = (
        "Resets your development database to a fresh state. "
        "All data will be deleted.")

    def add_arguments(self, parser):
        ahelp = (
            'Tells the resetdb command to NOT prompt the user for '
            'input of any kind.')
        parser.add_argument(
            '--noinput', action='store_false', dest='interactive',
            default=True, help=ahelp)

    def _cancel_reset(self):
        answer = None
        self.stdout.write(
            "Resetting the DB will destroy all current data. ")
        while not answer or answer not in "yn":
            answer = six.moves.input("Do you wish to proceed? [yN] ")
            if not answer:
                answer = "n"
            else:
                answer = answer[0].lower()
        return answer == "n"

    def _drop_table_stmt(self, dbconf):
        engine = dbconf["ENGINE"]
        if engine in CUSTOM_RESETDB_DROP_TABLES:
            return CUSTOM_RESETDB_DROP_TABLES[engine]
        return RESETDB_DROP_TABLES[engine]

    def _get_tables(self, db):
        tables = []
        out = six.StringIO()
        call_command('inspectdb', database=db, no_color=True, stdout=out)
        for line in out.getvalue().splitlines():
            line = line.strip()
            if line.startswith("db_table = '"):
                tablename = line.replace(
                    "db_table = '", "", 1).replace("'", "").strip()
                tables.append(tablename)
        return tuple(reversed(tables))

    def _drop_tables(self, tables, db, dt_stmt):
        with connections[db].cursor() as cursor:
            for table in tables:
                stmt = dt_stmt.format(table=table)
                cursor.execute(stmt)

    def handle(self, **options):
        print('verbosity: {}'.format(options['verbosity']))
        options.setdefault('verbosity', 0)
        if options.pop("interactive") and self._cancel_reset():
            return

        for db, dbconf in six.iteritems(settings.DATABASES):
            logger.info("Selecting DROP TABLE Statement for the engine...")
            dt_stmt = self._drop_table_stmt(dbconf)

            logger.info("Retrieving Existing Tables...")
            tables = self._get_tables(db)

            logger.info("Dropping Tables...")
            self._drop_tables(tables, db, dt_stmt)

            logger.info("Creating Database '{}'...".format(db))

            # Hack so that migrate can't find migrations files
            # this way, syncdb will be run instead of migrate.
            # This is preferable because
            # users who are used to running "otree resetdb"
            # may not know how to run 'otree makemigrations'.
            # This means their migration files will not be up to date,
            # ergo migrate will create tables with an outdated schema.

            # after the majority of oTree users have this new version
            # of resetdb, we can add a migrations/ folder to each app
            # in the sample games and the app template,
            # and deprecate resetdb
            # and instead use "otree makemigrations" and "otree migrate".

            # patch .migrations_module() to return a nonexistent module,
            # instead of app_name.migrations.
            # because this module is not found,
            # migration system will assume the app has no migrations,
            # and run syncdb instead.
            with mock.patch.object(
                    MigrationLoader,
                    'migrations_module',
                    return_value='migrations nonexistent hack'
            ):
                # note: In 1.9, will need to pass --run-syncdb flag
                call_command(
                    'migrate', database=db,
                    interactive=False, **options)

            # second call to 'migrate', simply to
            # fake migrations so that runserver doesn't complain
            # about unapplied migrations
            call_command(
                'migrate', database=db, fake=True,
                interactive=False, **options)
