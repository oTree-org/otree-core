import os

from sys import argv
from pathlib import Path
from typing import Optional
from importlib import import_module
import logging
from logging.config import dictConfig
from otree import __version__


# adapted from uvicorn
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            # we could use colorama to get coloring for windows. otherwise we get:
            # [32mINFO[0m:
            # "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(message)s",
            "use_colors": None,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',  # noqa: E501
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
    'root': {'handlers': ['default'], 'level': logging.INFO,},
}

dictConfig(LOGGING_CONFIG)

logger = logging.getLogger(__name__)


print_function = print

COMMAND_ALIASES = dict(
    test='bots',
    runprodserver='prodserver',
    webandworkers='prodserver1of2',
    runprodserver1of2='prodserver1of2',
    runprodserver2of2='prodserver2of2',
    timeoutworker='prodserver2of2',
    version='--version',
    help='--help',
)


def execute_from_command_line(*args, **kwargs):

    if len(argv) == 1:
        argv.append('help')

    cmd = argv[1]
    cmd = COMMAND_ALIASES.get(cmd, cmd)

    if cmd == '--version':
        print_function(__version__)
        return
    if cmd == '--help':
        print_function(MAIN_HELP_TEXT)
        return

    # [does the below caveat still apply without django?]
    # need to set env var rather than setting otree.common.USE_TIMEOUT_WORKER because
    # that module cannot be loaded yet.
    if cmd in ['prodserver', 'prodserver1of2']:
        os.environ['USE_TIMEOUT_WORKER'] = '1'

    if cmd in [
        'startproject',
        'version',
        '--version',
        'compilemessages',
        'makemessages',
        'unzip',
        'zip',
        'zipserver',
        'devserver',
    ]:
        # skip full setup.
        pass
    else:
        if cmd in ['devserver_inner', 'bots']:
            os.environ['OTREE_IN_MEMORY'] = '1'
        setup()
    warning = check_update_needed(Path('.').resolve().joinpath('requirements.txt'))
    if warning:
        logger.warning(warning)

    from otree.cli.base import call_command

    call_command(cmd, *argv[2:])


def setup():
    from otree import settings

    os.environ['LANGUAGE'] = settings.LANGUAGE_CODE_ISO

    from otree.database import init_orm  # noqa
    import gettext
    import locale

    # because the files are called django.mo
    gettext.textdomain('django')
    gettext.bindtextdomain('django', localedir=str(Path(__file__).parent / 'locale'))
    # locale is for number formatting etc.
    locale.setlocale(
        locale.LC_ALL, settings.LANGUAGE_CODE_ISO,
    )  # Use '' for auto, or force e.g. to 'en_US.UTF-8'

    init_orm()

    import otree.bots.browser

    otree.bots.browser.browser_bot_worker = otree.bots.browser.BotWorker()


def split_dotted_version(version):
    return [int(n) for n in version.split('.')]


def check_update_needed(
    requirements_path: Path, current_version=__version__
) -> Optional[str]:
    '''rewrote this without pkg_resources since that takes 0.4 seconds just to import'''

    if not requirements_path.exists():
        return

    for line in requirements_path.read_text('utf8').splitlines():
        if (not line.startswith('otree')) or ' ' in line or '\t' in line:
            continue
        for start in ['otree>=', 'otree[mturk]>=']:
            if line.startswith(start):
                version_dotted = line[len(start) :]
                try:

                    required_version = split_dotted_version(version_dotted)
                    installed_version = split_dotted_version(current_version)
                except ValueError:
                    return
                if required_version > installed_version:
                    return f'''This project requires a newer oTree version. Enter: pip3 install "{line}"'''


def send_termination_notice(PORT) -> int:
    # expensive imports. do it in here so that we don't delay devserver_inner
    from urllib.request import urlopen
    import urllib.error

    try:
        # send data= so it makes a post request
        # it seems using localhost is very slow compared to 127.0.0.1
        resp = urlopen(f'http://127.0.0.1:{PORT}/SaveDB', data=b'foo')
        return int(resp.read().decode('utf-8'))
    except urllib.error.URLError as exc:
        # - URLError may happen if the server didn't even start up yet
        #  (if you stop it right away)
        pass


MAIN_HELP_TEXT = '''
Available subcommands:

browser_bots
create_session
devserver
prodserver
prodserver1of2
prodserver2of2
resetdb
startapp
startproject
test
unzip
zip
zipserver
'''
