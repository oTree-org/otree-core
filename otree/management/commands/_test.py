#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from otree.test import core

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "oTree: Run the test bots for a session."
    args = '[session_type]'

    def handle(self, *args, **options):

        if len(args) > 1:
            raise CommandError(
                "Wrong number of arguments (expecting '{}')".format(self.args)
            )

        success, cov = core.run(args, True)

        exit_status = 0 if all(success.values()) else 1
        sys.exit(exit_status)

