import logging
import six

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connections, transaction
from otree import common_internal


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

                # need to hide the migrations/ folder so that Django thinks
                # it doesn't exist.
                # Tried setting MIGRATIONS_MODULES but doesn't work
                # (causes ModuleNotFoundError)
                common_internal.patch_migrations_module()

                call_command(
                    'migrate', database=db,
                    interactive=False, run_syncdb=True, **options)

        # mention the word 'columns' here, so people make the connection
        # between columns and resetdb, so that when they get a 'no such column'
        # error, they know how to fix it.
        # (An alternative is to generically catch "no such column" errors,
        # but I recall that this was difficult - because there were many
        # code paths or exception classes. Could re-investigate.)
        logger.info('Created new tables and columns.')
