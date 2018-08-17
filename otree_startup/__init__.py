import json
import logging
import re
import django.core.management
import django.conf
import os
import sys
from collections import OrderedDict, defaultdict
from django.conf import settings
from importlib import import_module
from django.core.management import get_commands, load_command_class
import django
from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.management.color import color_style
from django.utils import autoreload, six
from .settings import augment_settings
import otree


# REMEMBER TO ALSO UPDATE THE PROJECT TEMPLATE
from otree_startup.settings import get_default_settings

logger = logging.getLogger(__name__)


def print_settings_not_found_error():
    msg = (
        "Cannot find oTree settings. "
        "Please 'cd' to your oTree project folder, "
        "which contains a settings.py file."
    )
    logger.warning(msg)


def execute_from_command_line(*args, **kwargs):
    '''
    This is called if people use manage.py,
    or if people use the otree script.
    script_file is no longer used, but we need it for compat

    Given the command-line arguments, this figures out which subcommand is
    being run, creates a parser appropriate to that command, and runs it.
    '''

    argv = sys.argv

    # so that we can patch it easily
    settings = django.conf.settings

    if len(argv) == 1:
        # default command
        argv.append('help')

    subcommand = argv[1]

    if subcommand == 'runserver':
        sys.stdout.write(
            "Suggestion: use 'otree devserver' instead of 'otree runserver'. "
            "devserver automatically syncs your database.\n"
        )


    # Add the current directory to sys.path so that Python can find
    # the settings module.
    # when using "python manage.py" this is not necessary because
    # the entry-point script's dir is automatically added to sys.path.
    # but the 'otree' command script is located outside of the project
    # directory.
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())

    # to match manage.py
    # make it configurable so i can test it
    # note: we will never get ImproperlyConfigured,
    # because that only happens when DJANGO_SETTINGS_MODULE is not set
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    DJANGO_SETTINGS_MODULE = os.environ['DJANGO_SETTINGS_MODULE']

    # some commands don't need settings.INSTALLED_APPS
    try:
        configure_settings(DJANGO_SETTINGS_MODULE)
    except ImportSettingsError:
        if subcommand in [
            'startproject',
            'help', 'version', '--help', '--version', '-h',
            'compilemessages', 'makemessages',
            'upgrade_my_code', 'update_my_code'
        ]:
            if not settings.configured:
                settings.configure(**get_default_settings({}))
        # need to differentiate between an ImportError because settings.py
        # was not found, vs. ImportError because settings.py imports another
        # module that is not found.
        elif os.path.isfile('{}.py'.format(DJANGO_SETTINGS_MODULE)):
            raise
        else:
            print_settings_not_found_error()
            return

    runserver_or_devserver = subcommand in ['runserver', 'devserver']

    if runserver_or_devserver:
        # apparently required by restart_with_reloader
        # otherwise, i get:
        # python.exe: can't open file 'C:\oTree\venv\Scripts\otree':
        # [Errno 2] No such file or directory

        # this doesn't work if you start runserver from another dir
        # like python my_project/manage.py runserver. but that doesn't seem
        # high-priority now.
        sys.argv = ['manage.py'] + argv[1:]

        # previous solution here was using subprocess.Popen,
        # but changing it to modifying sys.argv changed average
        # startup time on my machine from 2.7s to 2.3s.

    # Start the auto-reloading dev server even if the code is broken.
    # The hardcoded condition is a code smell but we can't rely on a
    # flag on the command class because we haven't located it yet.

    if runserver_or_devserver and '--noreload' not in argv:
        try:
            autoreload.check_errors(do_django_setup)()
        except Exception:
            # The exception will be raised later in the child process
            # started by the autoreloader. Pretend it didn't happen by
            # loading an empty list of applications.
            apps.all_models = defaultdict(OrderedDict)
            apps.app_configs = OrderedDict()
            apps.apps_ready = apps.models_ready = apps.ready = True
    else:
        do_django_setup()

    if subcommand in ['help', '--help', '-h'] and len(argv) == 2:
        sys.stdout.write(main_help_text() + '\n')
    elif subcommand == 'help' and len(argv) >= 3:
        command_to_explain = argv[2]
        fetch_command(command_to_explain).print_help('otree', command_to_explain)
    elif subcommand in ("version", "--version"):
        sys.stdout.write(otree.__version__ + '\n')
        try:
            pypi_updates_cli()
        except:
            pass
    else:
        fetch_command(subcommand).run_from_argv(argv)


class ImportSettingsError(ImportError):
    pass


def configure_settings(DJANGO_SETTINGS_MODULE: str = 'settings'):
    # settings could already be configured if we are testing
    # execute_from_command_line
    if django.conf.settings.configured:
        return
    try:
        user_settings_module = import_module(DJANGO_SETTINGS_MODULE)
    except ImportError:
        raise ImportSettingsError
    user_settings_dict = {}
    user_settings_dict['BASE_DIR'] = os.path.dirname(
        os.path.abspath(user_settings_module.__file__))
    # this is how Django reads settings from a settings module
    for setting_name in dir(user_settings_module):
        if setting_name.isupper():
            setting_value = getattr(user_settings_module, setting_name)
            user_settings_dict[setting_name] = setting_value
    augment_settings(user_settings_dict)
    django.conf.settings.configure(**user_settings_dict)


def do_django_setup():
    try:
        django.setup()
    except Exception as exc:
        import colorama
        colorama.init(autoreset=True)
        print_colored_traceback_and_exit(exc)


def main_help_text() -> str:
    """
    Returns the script's main help text, as a string.
    """
    usage = [
        "",
        "Type 'otree help <subcommand>' for help on a specific subcommand.",
        "",
        "Available subcommands:",
    ]
    commands_dict = defaultdict(lambda: [])
    for name, app in six.iteritems(get_commands()):
        if app == 'django.core':
            app = 'django'
        else:
            app = app.rpartition('.')[-1]
        commands_dict[app].append(name)
    style = color_style()
    for app in sorted(commands_dict.keys()):
        usage.append("")
        usage.append(style.NOTICE("[%s]" % app))
        for name in sorted(commands_dict[app]):
            usage.append("    %s" % name)

    return '\n'.join(usage)


def fetch_command(subcommand: str) -> BaseCommand:
    """
    Tries to fetch the given subcommand, printing a message with the
    appropriate command called from the command line (usually
    "django-admin" or "manage.py") if it can't be found.
    override a few django commands in the case where settings not loaded.
    hard to test this because we need to simulate settings not being
    configured
    """
    if subcommand in ['startapp', 'startproject']:
        command_module = import_module(
            'otree.management.commands.{}'.format(subcommand))
        return command_module.Command()

    commands = get_commands()
    try:
        app_name = commands[subcommand]
    except KeyError:
        sys.stderr.write(
            "Unknown command: %r\nType 'otree help' for usage.\n"
            % subcommand
        )
        sys.exit(1)
    if isinstance(app_name, BaseCommand):
        # If the command is already loaded, use it directly.
        klass = app_name
    else:
        klass = load_command_class(app_name, subcommand)
    return klass


def check_pypi_for_updates() -> dict:
    '''return a dict because it needs to be json serialized for the AJAX
    response'''
    # need to import it so it can be patched outside
    import otree_startup
    if not otree_startup.PYPI_CHECK_UPDATES:
        return {'pypi_connection_error': True}
    # import only if we need it
    import requests

    logging.getLogger("requests").setLevel(logging.WARNING)

    try:
        response = requests.get(
            'https://pypi.python.org/pypi/otree/json',
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
            'Your otree package is out-of-date '
            '(version {}; latest is {}). '
            'You should upgrade with:\n '
            '"pip3 install --upgrade otree"\n '
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


PYPI_CHECK_UPDATES = True


def print_colored_traceback_and_exit(exc):
    import traceback
    from termcolor import colored
    import sys


    def highlight(string):
        return colored(string, 'white', 'on_blue')

    # before we used BASE_DIR but apparently that setting was not set yet
    # (not sure why)
    # so use os.getcwd() instead.
    # also, with BASE_DIR, I got "unknown command: devserver", as if
    # the list of commands was not loaded.
    current_dir = os.getcwd()

    frames = traceback.extract_tb(sys.exc_info()[2])
    new_frames = []
    for frame in frames:
        filename, lineno, name, line = frame
        if current_dir in filename:
            filename = highlight(filename)
            line = highlight(line)
        new_frames.append([filename, lineno, name, line])
    # taken from django source?
    lines = ['Traceback (most recent call last):\n']
    lines += traceback.format_list(new_frames)
    final_lines = traceback.format_exception_only(type(exc), exc)
    # filename is only available for SyntaxError
    if isinstance(exc, SyntaxError) and current_dir in exc.filename:
        final_lines = [highlight(line) for line in final_lines]
    lines += final_lines
    for line in lines:
        sys.stdout.write(line)
    sys.exit(-1)