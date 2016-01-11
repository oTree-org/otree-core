#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================

import os
from django.core.management.commands import startproject
import otree

# =============================================================================
# LOGGER
# =============================================================================

from django.utils import six


class Command(startproject.Command):
    help = (
        "Creates a new oTree project.")

    def add_arguments(self, parser):
        ahelp = (
            'Tells the command to NOT prompt the user '
            'for input of any kind.')
        parser.add_argument('name', help='Name of the project.')
        parser.add_argument(
            '--noinput', action='store_false', dest='interactive',
            default=True, help=ahelp)

    def handle(self, *args, **options):
        if options.get('interactive'):
            answer = None
            self.stdout.write(
                "Please choose whether to create a new project with the "
                "bundle of sample games, or create a minimal project folder "
                "with no sample games.)")
            while not answer or answer not in "yn":
                answer = six.moves.input("Include sample games? [Yn] ")
                if not answer:
                    answer = "y"
                    break
                else:
                    answer = answer[0].lower()
            sample_games = answer == "y"
        else:
            sample_games = True

        if sample_games:
            location = "https://github.com/oTree-org/oTree/archive/master.zip"
        else:
            location = os.path.join(
                os.path.dirname(otree.__file__), 'project_template')
        options.setdefault('template', location)
        super(Command, self).handle(*args, **options)
