import os
import platform
import subprocess
import sys

import django
import django.core.management
from django.core.management.base import CommandError
from django.core.management.color import color_style
from django.conf import settings

import otree
import otree.management.deploy.heroku


# =============================================================================
# CONSTANTS
# =============================================================================

MANAGE_URL = (
    "https://raw.githubusercontent.com/oTree-org/oTree/master/manage.py")


IGNORE_APPS_COMMANDS = frozenset(("version", "--version", "startapp", "help"))


# =============================================================================
# FUNCTIONS
# =============================================================================

def otree_and_django_version(*args, **kwargs):
    otree_ver = otree.get_version()
    django_ver = django.get_version()
    return "oTree: {} - Django: {}".format(otree_ver, django_ver)


def execute_from_command_line(arguments, script_file):
    # Workaround for windows. Celery (more precicely the billard library) will
    # complain if the script you are using to initialize celery does not end
    # on '.py'. That's why we require a manage.py file to be around.
    # See https://github.com/celery/billiard/issues/129 for more details.

    cond = (
        platform.system() == 'Windows' and not
        script_file.lower().endswith('.py'))

    if cond:

        scriptdir = os.path.dirname(os.path.abspath(script_file))
        managepy = os.path.join(scriptdir, 'manage.py')
        if not os.path.exists(managepy):
            error_lines = []

            error_lines.append(
                "It seems that you do not have a file called 'manage.py' in "
                "your current directory. This is a requirement when using "
                "otree on windows."
            )
            error_lines.append("")
            error_lines.append("")
            error_lines.append(
                "Please download the file {url} and save it as 'manage.py' in "
                "the directory {directory}".format(
                    url=MANAGE_URL, directory=scriptdir))
            raise CommandError("\n".join(error_lines))
        args = [sys.executable] + [managepy] + sys.argv[1:]
        process = subprocess.Popen(args,
                                   stdin=sys.stdin,
                                   stdout=sys.stdout,
                                   stderr=sys.stderr)
        return_code = process.wait()
        sys.exit(return_code)

    # in issue #300 we agreed that sslserver should
    # run only if user has specified credentials for AWS
    if (len(sys.argv) >= 2 and sys.argv[1] == 'runserver' and
       settings.AWS_ACCESS_KEY_ID):
            sys.argv[1] = 'runsslserver'

    # only monkey patch when is necesary
    if "version" in arguments or "--version" in arguments:
        sys.stdout.write(otree_and_django_version() + '\n')
    else:
        django.core.management.execute_from_command_line(sys.argv)


def otree_cli():
    """
    This function is the entry point for the ``otree`` console script.
    """

    # We need to add the current directory to the python path as this is not
    # set by default when no using "python <script>" but a standalone script
    # like ``otree``.
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

    try:
        from django.conf import settings
        settings.INSTALLED_APPS
    except ImportError:
        style = color_style()
        msg = style.ERROR(
            "Cannot import otree settings.\n"
            "Please make sure that you are in the base directory of your "
            "oTree library checkout. This directory contains a settings.py "
            "and a manage.py file.")
        print(msg)
        sys.exit(1)

    # some commands don't need the setings.INSTALLED_APPS
    # see: https://github.com/oTree-org/otree-core/issues/388
    ignore_apps = IGNORE_APPS_COMMANDS.intersection(sys.argv)
    if ignore_apps:
        settings.INSTALLED_APPS = tuple(settings.NO_EXPERIMENT_APPS)

    execute_from_command_line(sys.argv, 'otree')


def otree_heroku_cli():
    """
    This function is the entry point for the ``otree-heroku`` console script.
    """

    # We need to add the current directory to the python path as this is not
    # set by default when no using "python <script>" but a standalone script
    # like ``otree``.
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    style = color_style()

    try:
        from django.conf import settings
        settings.INSTALLED_APPS
    except ImportError:
        print(style.ERROR(
            "Cannot import otree settings. Please make sure that you are "
            "in the base directory of your oTree library checkout. "
            "This directory contains a settings.py and a manage.py file."))
        sys.exit(1)

    otree.management.deploy.heroku.execute_from_command_line(sys.argv)
