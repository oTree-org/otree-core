#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connections, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.autodetector import MigrationAutodetector

import six
from unittest import mock


# =============================================================================
# LOGGER
# =============================================================================

logger = logging.getLogger('otree')


def drop_tables_command(db_engine):
    if 'sqlite3' in db_engine:
        return 'DROP TABLE {table};'
    if 'oracle' in db_engine:
        return 'DROP TABLE "{table}" CASCADE CONSTRAINTS;'
    if 'postgres' in db_engine:
        return 'DROP TABLE "{table}" CASCADE;'
    if 'mysql' in db_engine:
        return (
            'SET FOREIGN_KEY_CHECKS = 0;'
            'DROP TABLE {table} CASCADE;'
            'SET FOREIGN_KEY_CHECKS = 1;')
    raise ValueError(
        'resetdb command does not recognize DB engine "{}"'.format(db_engine))


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

    def _confirm(self):
        self.stdout.write(
            "This will delete and recreate your database. ")
        answer = six.moves.input("Proceed? (y or n): ")
        if answer:
            return answer[0].lower() == 'y'
        return False

    def _drop_table_stmt(self, dbconf):
        engine = dbconf["ENGINE"]
        return drop_tables_command(engine)

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
        if options.pop("interactive") and not self._confirm():
            self.stdout.write('Canceled.')
            return

        for db, dbconf in six.iteritems(settings.DATABASES):
            db_engine = dbconf['ENGINE']
            if 'postgresql' in db_engine.lower():
                db_engine = 'PostgreSQL'
            elif 'sqlite' in db_engine.lower():
                db_engine = 'SQLite'
            elif 'mysql' in db_engine.lower():
                db_engine = 'MySQL'
            logger.info("Database engine: {}".format(db_engine))
            dt_stmt = self._drop_table_stmt(dbconf)

            logger.info("Retrieving Existing Tables...")
            tables = self._get_tables(db)

            logger.info("Dropping Tables...")

            # use a transaction to prevent the DB from getting in an erroneous
            # state, which can result in a different error message when resetdb
            # is run again, making the original error hard to trace.
            with transaction.atomic(
                    using=connections[db].alias,
                    savepoint=connections[db].features.can_rollback_ddl
            ):
                self._drop_tables(tables, db, dt_stmt)

                logger.info("Creating Database '{}'...".format(db))

                self.syncdb(db, options)

                # second call to 'migrate', simply to
                # fake migrations so that runserver doesn't complain
                # about unapplied migrations
                # note: In 1.9, will need to pass --run-syncdb flag

                call_command(
                    'migrate', database=db, fake=True,
                    interactive=False, **options)

        # mention the word 'columns' here, so people make the connection
        # between columns and resetdb, so that when they get a 'no such column'
        # error, they know how to fix it.
        # (An alternative is to generically catch "no such column" errors,
        # but I recall that this was difficult - because there were many
        # code paths or exception classes. Could re-investigate.)
        logger.info('Created new tables and columns.')

    @mock.patch.object(
        MigrationLoader, 'migrations_module',
        return_value='migrations nonexistent hack')
    @mock.patch.object(
        MigrationAutodetector, 'changes', return_value=False)
    def syncdb(self, db, options, *mocked_args):
        '''
        patch .migrations_module() to return a nonexistent module,
        instead of app_name.migrations.
        because this module is not found,
        migration system will assume the app has no migrations,
        and run syncdb instead.

        Hack so that migrate can't find migrations files
        this way, syncdb will be run instead of migrate.
        This is preferable because
        users who are used to running "otree resetdb"
        may not know how to run 'otree makemigrations'.
        This means their migration files will not be up to date,
        ergo migrate will create tables with an outdated schema.

        after the majority of oTree users have this new version
        of resetdb, we can add a migrations/ folder to each app
        in the sample games and the app template,
        and deprecate resetdb
        and instead use "otree makemigrations" and "otree migrate".

        also, syncdb is faster than migrate, and there is no
        advantage to migrate since it's being run on a newly
        created DB anyway.

        also patch MigrationAutodetector.changes() to suppress the warning
        "Your models have changes that are not yet reflected in a migration..."
        '''
        call_command(
            'migrate', database=db,
            interactive=False, **options)
