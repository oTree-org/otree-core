import logging
import os
import sys
from logging.config import dictConfig
from pathlib import Path
from sys import argv

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
        "uvicorn.error": {"level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        # otherwise we get 'connection open', 'connection closed' on each page
        "websockets.server": {"propagate": False, "level": "WARNING"},
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
    if 'devserver' in cmd:
        os.environ['USE_TEMPLATE_RELOADER'] = '1'

    if cmd in [
        'startproject',
        'version',
        '--version',
        'unzip',
        'zip',
        'zipserver',
        'devserver',
        'update_my_code',
        'remove_self',
        'remove_self_finalize',
    ]:
        # skip full setup.
        pass
    else:
        if cmd in ['devserver_inner', 'bots']:
            os.environ['OTREE_IN_MEMORY'] = '1'
        setup()

    from otree.cli.base import call_command

    call_command(cmd, *argv[2:])


MSG_V5_WELCOME = """
Welcome to oTree Lite!
To ensure this project runs properly on oTree Lite:

1)   Run "otree update_my_code" and fix any warning messages.
2)   Delete 'db.sqlite3' and the folder '__temp_migrations'.

oTree Lite is generally compatible with oTree 3.x but there may be small differences. 
Note that it does not use Django.
If you want to go back to oTree 3.x, enter: pip3 install -U "otree<5"
"""


def setup():
    if Path('__temp_migrations').exists():
        sys.exit(MSG_V5_WELCOME)

    from otree import settings

    init_i18n(settings.LANGUAGE_CODE_ISO)

    from otree.database import init_orm  # noqa

    check_for_sentry()
    init_orm()

    import otree.bots.browser

    otree.bots.browser.browser_bot_worker = otree.bots.browser.BotWorker()


def init_i18n(LANGUAGE_CODE_ISO):
    os.environ['LANGUAGE'] = LANGUAGE_CODE_ISO
    import gettext

    # because the files are called django.mo
    gettext.textdomain('django')
    gettext.bindtextdomain('django', localedir=str(Path(__file__).parent / 'locale'))
    if Path('_locale').is_dir():
        gettext.bindtextdomain('messages', localedir='_locale')
        gettext.textdomain('messages')




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


def check_for_sentry():
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    if SENTRY_DSN:
        try:
            import sentry_sdk
        except ModuleNotFoundError:
            sys.exit(
                'For Sentry to work, you need to add sentry_sdk to your requirements.txt.'
            )
        from sentry_sdk.utils import json_dumps
        from urllib.request import urlopen
        import urllib.error

        def before_send(event, hint):
            otree_post_url = os.getenv('OTREE_ERROR_REPORT_ENDPOINT')
            if otree_post_url:
                try:
                    urlopen(otree_post_url, data=json_dumps(event), timeout=0.5)
                except urllib.error.URLError:
                    # in case timeout is raised etc
                    pass
            return event

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            # 2018-11-24: breadcrumbs were causing memory leaks when doing queries,
            # especially when creating sessions, which construct hugely verbose
            # queries with bulk_create.
            # however, i could only clearly observe the difference this line makes
            # when testing
            # on a script that bulk_created thousands of non-otree models.
            # when testing on a live server, things are more ambiguous.
            # maybe just refreshing the page several times after creating a session
            # is enough to reset memory to reasnoable levels?
            # disabling also may make things faster...
            # in anecdotal test, 40 vs 50 seconds
            max_breadcrumbs=0,
            release=__version__,
            before_send=before_send,
        )


MAIN_HELP_TEXT = '''
Available subcommands:

browser_bots
create_session
devserver
prodserver
prodserver1of2
prodserver2of2
remove_self
resetdb
startapp
startproject
test
unzip
update_my_code
zip
zipserver
'''
