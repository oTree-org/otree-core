#!/usr/bin/env python
# -*- coding: utf-8 -*-

# import warnings

from .bots import Command as BotCommand


class Command(BotCommand):

    def handle(self, **options):
        # warnings.warn(
        #     "The command is deprectated please use 'otree bots' instead",
        #     DeprecationWarning)
        super(Command, self).handle(**options)
