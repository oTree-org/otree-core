#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================

import sys
import os
import platform
import string
import errno

from django.core.management.commands import startproject

import six

import otree
from otree.common_internal import check_pypi_for_updates

# =============================================================================
# CONSTANTS
# =============================================================================

IMPLEMENTATIONS_ALIAS = {
    "CPython": "python"
}

def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise exception


# =============================================================================
# COMMAND
# =============================================================================

class Command(startproject.Command):
    help = ("Creates a new oTree project.")

    def render_runtime(self, options):
        project_name, target = options['name'], options['directory']
        if target is None:
            project_root_dir = os.path.join(os.getcwd(), project_name)
        else:
            project_root_dir = os.path.abspath(os.path.expanduser(target))

        imp = platform.python_implementation()
        implementation_name = IMPLEMENTATIONS_ALIAS.get(imp, imp).lower()
        version = ".".join(map(str, sys.version_info[:3]))
        runtime_string = "{}-{}\n".format(implementation_name, version)

        runtime_path = os.path.join(project_root_dir, "runtime.txt")
        with open(runtime_path, "w") as fp:
            fp.write(runtime_string)

        # for each app in the project folder,
        # add a migrations folder
        # we do it here instead of modifying the games repo directly,
        # because people on older versions of oTree also install
        # from the same repo,
        # and the old resetdb chokes when it encounters an app with migrations
        subfolders = next(os.walk(project_root_dir))[1]
        for subfolder in subfolders:
            # ignore folders that start with "." or "_" etc...
            if subfolder[0] in string.ascii_letters:
                migrations_folder_path = os.path.join(project_root_dir, subfolder, 'migrations')
                make_sure_path_exists(migrations_folder_path)
                init_file_path = os.path.join(migrations_folder_path, '__init__.py')
                with open(init_file_path, 'w') as f:
                    f.write('')

    def handle(self, *args, **options):
        answer = None
        while not answer or answer not in "yn":
            answer = six.moves.input("Include sample games? (y or n): ")
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

        self.render_runtime(options)
        check_pypi_for_updates()
