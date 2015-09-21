#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================

import logging
import importlib

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connections
from django.db.migrations import loader


from otree import session


# =============================================================================
# LOGGER
# =============================================================================

logger = logging.getLogger('otree')


import os
import sys

from django.core.management.base import NoArgsCommand
from django.utils import six


class Command(NoArgsCommand):
    help = (
        "Resets your development database to a fresh state. "
        "All data will be deleted.")

    def add_arguments(self, parser):
        ahelp = (
            'Tells the resetdb command to NOT prompt the user '
            'for input of any kind.')
        parser.add_argument(
            '--noinput', action='store_false', dest='interactive',
            default=True, help=ahelp)

    def handle_noargs(self, **options):
        self.interactive = options.get('interactive')

        default_db = settings.DATABASES['default']
        if 'sqlite' not in default_db['ENGINE']:
            sys.stderr.write(
                "ERROR: cannot set back a database that is using the "
                "{backend} backend. We only support sqlite databases so far. "
                "You should drop the database and then run "
                "'manage.py migrate'. "
                "Example: \n\n"
                "./manage.py sqlclear | ./manage.py dbshell\n"
                "./manage.py migrate\n\n"
                .format(backend=default_db['ENGINE']))
            sys.exit(1)

        db_file_name = default_db['NAME']
        # Delete DB file if it already exists.
        if os.path.exists(db_file_name):
            if self.interactive:
                answer = None
                self.stdout.write(
                    "Resetting the DB will destroy all current data. "
                    "The DB file {0} will be deleted.\n".format(db_file_name))
                while not answer or answer not in "yn":
                    answer = six.moves.input("Do you wish to proceed? [yN] ")
                    if not answer:
                        answer = "n"
                        break
                    else:
                        answer = answer[0].lower()
                if answer != "y":
                    return

            self.stdout.write("Deleting {0} ...\n".format(db_file_name))
            os.unlink(db_file_name)

        call_command('migrate', interactive=self.interactive)


# =============================================================================
# COMMAND
# =============================================================================

# not working yet because of issue #386
# so using old version above instead
class NewVersionCommand(BaseCommand):
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

    def _get_apps(self):
        napps, mapps = set(), set()
        for label in session.app_labels_from_sessions():
            migration_module = loader.MigrationLoader.migrations_module(label)
            try:
                importlib.import_module(migration_module)
            except ImportError:
                napps.add(label)
            else:
                mapps.add(label)
        return map(tuple, (napps, mapps))

    def handle(self, **options):

        self.interactive = options.pop("interactive")
        if self.interactive:
            answer = None
            self.stdout.write(
                "Resetting the DB will destroy all current data. ")
            while not answer or answer not in "yn":
                answer = six.moves.input("Do you wish to proceed? [yN] ")
                if not answer:
                    answer = "n"
                    break
                else:
                    answer = answer[0].lower()
            if answer != "y":
                return

        # Extract existing oTree apps
        apps, mapps = self._get_apps()

        # Try to make the migrations of all oTree apps with migrations
        if mapps:
            msg = "Making migrations of apps: {}".format("-".join(mapps))
            logger.info(msg)
            call_command('makemigrations', *mapps)

        for db in six.iterkeys(settings.DATABASES):

            # removing all data from existing databases
            logger.info("Resetting database '{}'".format(db))
            try:
                call_command(
                    'flush', database=db, interactive=False, **options)
            except RuntimeError:
                msg = "Database '{}' data is inconsistence".format(db)
                logger.warning(msg)
            else:
                # If flush work is because the database exist and if we have
                # oTree apps without migrations we need to drop the tables
                if apps:
                    logger.info("Dropping Tables...")
                    out = six.StringIO()
                    call_command(
                        'sqlclear', *apps, database=db,
                        no_color=True, stdout=out)
                    with connections[db].cursor() as cursor:
                        for stmt in out.getvalue().splitlines():
                            stmt = stmt.strip()
                            if stmt:
                                cursor.execute(stmt)

            # finally apply all migrations
            call_command(
                'migrate', database=db, fake_initial=True,
                interactive=False, **options)
