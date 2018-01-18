from __future__ import print_function
from importlib import import_module
import json
import logging
import subprocess
import os
import re
import sys
import django
import django.core.management
import requests
import django.conf

import otree
from otree.settings import get_default_settings


class OTreeManagementUtility(django.core.management.ManagementUtility):
    def fetch_command(self, subcommand):
        '''
        override a few django commands in the case where settings not loaded
        hard to test this because we need to simulate settings not being
        configured
        '''
        if subcommand in ['startapp', 'startproject']:
            command_module = import_module(
                'otree.management.commands.{}'.format(subcommand))
            return command_module.Command()
        return super().fetch_command(subcommand)

def otree_and_django_version(*args, **kwargs):
    otree_ver = otree.get_version()
    django_ver = django.get_version()
    return "oTree: {} - Django: {}".format(otree_ver, django_ver)


class SettingsNotFoundError(Exception):
    pass


SETTINGS_NOT_FOUND_MESSAGE = (
    "Cannot import otree settings.\n"
    "Please make sure that you are in the root directory of your "
    "oTree project. This directory contains a settings.py "
    "and a manage.py file.")


def otree_cli():
    """
    This function is the entry point for the ``otree`` console script.
    """
    argv = sys.argv.copy()
    # so that we can patch it easily
    settings = django.conf.settings

    if len(argv) == 1:
        # default command
        argv.append('help')

    subcommand = argv[1]

    # We need to add the current directory to the python path as this is not
    # set by default when no using "python <script>" but a standalone script
    # like ``otree``.
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())

    # to match manage.py
    # make it configurable so i can test it
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    DJANGO_SETTINGS_MODULE = os.environ['DJANGO_SETTINGS_MODULE']

    # some commands don't need settings.INSTALLED_APPS
    # see: https://github.com/oTree-org/otree-core/issues/388
    try:
        # LazySettings object will try to import DJANGO_SETTINGS_MODULE
        settings.INSTALLED_APPS
    except ImportError as exc:
        if subcommand in [
            # 2017-10-23: why is startapp here?
            # why would you start an app without a project?
            # maybe it's inside a subfolder?
            'startproject',
            'help', 'version', '--help', '--version', '-h',
            'compilemessages', 'makemessages',
        ]:
            settings.configure(**get_default_settings({}))
        # need to differentiate between an ImportError because settings.py
        # was not found, vs. ImportError because settings.py imports another
        # module that is not found.
        elif os.path.isfile('{}.py'.format(DJANGO_SETTINGS_MODULE)):
            raise
        else:
            raise SettingsNotFoundError(SETTINGS_NOT_FOUND_MESSAGE)

    if subcommand in ['run', 'runserver']:
        # apparently required by restart_with_reloader
        # otherwise, i get:
        # python.exe: can't open file 'C:\oTree\venv\Scripts\otree':
        # [Errno 2] No such file or directory

        args = [sys.executable, 'manage.py'] + argv[1:]
        process = subprocess.Popen(args,
                                   stdin=sys.stdin,
                                   stdout=sys.stdout,
                                   stderr=sys.stderr)
        return_code = process.wait()
        sys.exit(return_code)

    execute_from_command_line(argv)


def execute_from_command_line(argv, script_file=None):
    '''script_file is no longer used, but we need it for compat'''

    if len(argv) == 1:
        # default command
        argv.append('help')
    subcommand = argv[1]

    # only monkey patch when is necesary
    if subcommand in ("version", "--version"):
        sys.stdout.write(otree_and_django_version() + '\n')
        try:
            pypi_updates_cli()
        except:
            pass
    else:
        utility = OTreeManagementUtility(argv)
        utility.execute()


def check_pypi_for_updates() -> dict:
    '''return a dict because it needs to be json serialized for the AJAX
    response'''
    # MUST IMPORT HERE, because otree.management.cli is imported before
    # django is loaded
    from otree import common_internal
    if not common_internal.PYPI_CHECK_UPDATES:
        return {}

    logging.getLogger("requests").setLevel(logging.WARNING)

    try:
        response = requests.get(
            'http://pypi.python.org/pypi/otree-core/json',
            timeout=5,
        )
        assert response.ok
        data = json.loads(response.content.decode())
    except:
        # could be requests.exceptions.Timeout
        # or another error (404/500/firewall issue etc)
        return {'pypi_connection_error': True}

    semver_re = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')

    installed_dotted = otree.__version__
    installed_match = semver_re.match(installed_dotted)

    if installed_match:
        # compare to the latest stable release

        installed_tuple = [int(n) for n in installed_match.groups()]

        releases = data['releases']
        newest_tuple = [0, 0, 0]
        newest_dotted = ''
        for release in releases:
            release_match = semver_re.match(release)
            if release_match:
                release_tuple = [int(n) for n in release_match.groups()]
                if release_tuple > newest_tuple:
                    newest_tuple = release_tuple
                    newest_dotted = release
        newest = newest_tuple
        installed = installed_tuple

        update_needed = (newest > installed and (
                newest[0] > installed[0] or newest[1] > installed[1] or
                newest[2] - installed[2] >= 8))

    else:
        # compare to the latest release, whether stable or not
        newest_dotted = data['info']['version'].strip()
        update_needed = newest_dotted != installed_dotted

    if update_needed:
        update_message = (
            'Your otree-core package is out-of-date '
            '(version {}; latest is {}). '
            'You should upgrade with:\n '
            '"pip3 install --upgrade otree-core"\n '
            'and update your requirements_base.txt.'.format(
                installed_dotted, newest_dotted))
    else:
        update_message = ''
    return {
        'pypi_connection_error': False,
        'update_needed': update_needed,
        'installed_version': installed_dotted,
        'newest_version': newest_dotted,
        'update_message': update_message,
    }


def pypi_updates_cli():
    result = check_pypi_for_updates()
    if result['pypi_connection_error']:
        return
    if result['update_needed']:
        print(result['update_message'])
