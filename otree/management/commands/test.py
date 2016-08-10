#!/usr/bin/env python
# -*- coding: utf-8 -*-

from otree import deprecate
from .bots import Command as BotCommand


class Command(BotCommand):

    def handle(self, **options):
        deprecate.dwarning(
            "The command is deprectated please use 'otree bots' instead")
        super(Command, self).handle(**options)
