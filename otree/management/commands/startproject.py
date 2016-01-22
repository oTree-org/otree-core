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

    def handle(self, *args, **options):
        answer = None
        while not answer or answer not in "yn":
            answer = six.moves.input("Include sample games? (y or n)")
            if not answer:
                answer = "y"
                break
            else:
                answer = answer[0].lower()

        if answer == "y":
            location = "https://github.com/oTree-org/oTree/archive/master.zip"
        else:
            location = os.path.join(
                os.path.dirname(otree.__file__), 'project_template')
        if options.get('template', None) is None:
            options['template'] = location
        super(Command, self).handle(*args, **options)
