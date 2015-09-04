#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

import six

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, connections

logger = logging.getLogger('otree')

class Command(BaseCommand):
    help = (
        "Resets your development database to a fresh state. "
        "All data will be deleted.")

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument(
            'session_name', nargs='*',
            help='If omitted, all sessions in SESSION_CONFIGS are run')

    def handle(self, **options):

        import ipdb; ipdb.set_trace()

        for db in six.iterkeys(settings.DATABASES):
            logger.info("Resetting database '{}'".format(db))
            try:
                call_command(
                    'flush', database=db, interactive=False, **options)
            except RuntimeError:
                logger.error("Database '{}' data is inconsistence".format(db))
            call_command('migrate', database=db, interactive=False, **options)
