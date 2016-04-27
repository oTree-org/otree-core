#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================

import sys
import os
import platform
import shutil
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


# =============================================================================
# COMMAND
# =============================================================================


def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise exception

class Command(startproject.Command):
    help = ("Creates a new oTree project.")

    def modify_project_files(self, options):
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

        # overwrite Procfile with new channels/asgi one
        procfile_path = os.path.join(
            self.core_project_template_path, 'Procfile')
        shutil.copy(procfile_path, project_root_dir)

        # for each app in the project folder,
        # add a migrations folder

        subfolders = next(os.walk('.'))[1]
        for subfolder in subfolders:
            if subfolder[0] in string.ascii_letters:
                # FIXME - add a migrations folder
                pass


    def handle(self, *args, **options):
        answer = None
        while not answer or answer not in "yn":
            answer = six.moves.input("Include sample games? (y or n): ")
            if not answer:
                answer = "y"
                break
            else:
                answer = answer[0].lower()

        self.core_project_template_path = os.path.join(
                os.path.dirname(otree.__file__), 'project_template')
        if answer == "y":
            project_template_path = "https://github.com/oTree-org/oTree/archive/master.zip"
        else:
            project_template_path = self.core_project_template_path
        if options.get('template', None) is None:
            options['template'] = project_template_path
        super(Command, self).handle(*args, **options)


        self.modify_project_files(options)
        try:
            check_pypi_for_updates()
        except:
            pass
