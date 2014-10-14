#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, sys


base_path = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, base_path)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")


default_test_apps = [
    'tests',
]


def runtests(*args):
    from django.core.management.commands.test import Command

    test_command = Command()
    test_apps = list(args or default_test_apps)
    test_command.execute(verbosity=1, *test_apps)


if __name__ == '__main__':
    runtests(*sys.argv[1:])
