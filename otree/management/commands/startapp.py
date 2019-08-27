#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from django.core.management.commands import startapp

import otree
from otree_startup import pypi_updates_cli


class Command(startapp.Command):
    def get_default_template(self):
        return os.path.join(
            os.path.dirname(otree.__file__), 'app_template')

    def handle(self, *args, **options):
        options['template'] = self.get_default_template()
        super().handle(*args, **options)
        try:
            pypi_updates_cli()
        except:  # noqa
            pass  # noqa
        self.stdout.write('Created app folder.')
