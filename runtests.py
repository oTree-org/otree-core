#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, sys


base_path = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, base_path)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")


from django.core.management import execute_from_command_line


default_test_apps = [
    'tests',
]


def runtests(*args):
    test_apps = list(args or default_test_apps)
    execute_from_command_line([sys.argv[0], 'test', '--verbosity=1'] + test_apps)


if __name__ == '__main__':
    runtests(*sys.argv[1:])
