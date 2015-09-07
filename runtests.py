#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys


base_path = os.path.dirname(os.path.abspath(__file__))
tests_path = os.path.join(base_path, "tests")

sys.path.insert(0, tests_path)
sys.path.insert(0, base_path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

default_test_apps = [
    'tests',
]


def runtests(*verbosity):
    import django
    django.setup()

    from django.conf import settings, global_settings
    from django.core.management.commands.test import Command

    settings.STATICFILES_STORAGE = global_settings.STATICFILES_STORAGE

    test_command = Command()
    verbosity = int(verbosity[0] if verbosity else 2)
    test_command.execute(*default_test_apps, verbosity=verbosity)


if __name__ == '__main__':
    runtests(*sys.argv[1:])
