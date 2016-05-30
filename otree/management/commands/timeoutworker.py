#!/usr/bin/env python
# -*- coding: utf-8 -*-

# run the worker to enforce page timeouts
# even if the user closes their browser
from huey.contrib.djhuey.management.commands.run_huey import (
    Command as HueyCommand
)


class Command(HueyCommand):
    pass
