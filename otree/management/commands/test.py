#!/usr/bin/env python
# -*- coding: utf-8 -*-

from otree import deprecate
from .bots import Command  # noqa


deprecate.dwarning(
    "The command is deprectated please use 'otree bots' instead")
