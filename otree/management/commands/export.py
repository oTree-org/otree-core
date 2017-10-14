#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import sys

from django.core.management.base import BaseCommand, CommandError

from otree import export


class Command(BaseCommand):
    help = 'Export data from the experiments'

    def add_arguments(self, parser):
        parser.add_argument(
            "--output", "-o", dest="output",
            type=argparse.FileType('w'), default=sys.stdout)

        commands = parser.add_mutually_exclusive_group(required=True)
        commands.add_argument(
            "--all", dest="command", action="store_const", const=["wide"],
            help=("Data for all apps in one file. There is one row per "
                  "participant; different apps and rounds are stacked "
                  "horizontally. This format is useful if you want to "
                  "correlate participant's behavior in one app with their "
                  "behavior in another app."))
        commands.add_argument(
            "--time", dest="command", action="store_const",
            const=["time_expend"], help="Time spent on each page in csv")

        commands.add_argument(
            "--app", dest="command", action="store",
            type=lambda v: ["per_app", v], metavar="APP-NAME",
            help=("Per-app data. "
                  "These files contain a row for each player in the given "
                  "app. If there are multiple rounds, there will be multiple "
                  "rows for the same participant. This format is useful if "
                  "you are mainly interested in one app, or if you want to "
                  "correlate data between rounds of the same app."))
        commands.add_argument(
            "--doc", dest="command", action="store",
            type=lambda v: ["app_doc", v], metavar="APP-NAME",
            help=("Per-app documentation data. "
                  "These files contain a row for each player in the given "
                  "app. If there are multiple rounds, there will be multiple "
                  "rows for the same participant. This format is useful if "
                  "you are mainly interested in one app, or if you want to "
                  "correlate data between rounds of the same app."))

    def _fext(self, fp):
        fname = getattr(fp, "name", "")
        return os.path.splitext(fname)[-1][1:] or "csv"

    def wide(self, fp):
        fext = self._fext(fp)
        export.export_wide(fp, file_extension=fext)

    def per_app(self, fp, app_name):
        fext = self._fext(fp)
        export.export_app(app_name, fp, file_extension=fext)

    def app_doc(self, fp, app_name):
        export.export_docs(fp, app_name)

    def time_expend(self, fp):
        fext = self._fext(fp)
        if fext != "csv":
            raise CommandError("time expende can only be exported to csv")
        export.export_time_spent(fp)

    def handle(self, *args, **options):
        output = options["output"]

        # extract the command and split in different arguments if is necessary
        command = options["command"]
        command, params = (
            (command[0], command[1:])
            if len(command) > 1 else
            (command[0], []))

        method = getattr(self, command, None)
        if method is None:
            raise CommandError('Command "{}" does not exist'.format(command))
        if params:
            method(output, *params)
        else:
            method(output)
