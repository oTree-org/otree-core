import logging
import json
import os

import sys
import time
from enum import Enum
from subprocess import check_output, Popen
from urllib.parse import urljoin

from otree import settings
from otree.asgi import reverse

import otree.channels.utils as channel_utils
from otree.session import SESSION_CONFIGS_DICT
from otree.common import get_admin_secret_code

AUTH_FAILURE_MESSAGE = """
Could not login to the server using your ADMIN_USERNAME
and ADMIN_PASSWORD from settings.py. If you are testing
browser bots on a remote server, make sure the username
and password on your local oTree installation match that
on the server.
"""

REST_KEY = os.getenv('OTREE_REST_KEY')

logger = logging.getLogger(__name__)

try:
    from requests import session as requests_session
    from ws4py.client.threadedclient import WebSocketClient
except ModuleNotFoundError:
    sys.exit(
        'To use command-line browser bots, you need to pip install "requests" and "ws4py" locally. '
    )


class OSEnum(Enum):
    windows = 'windows'
    mac = 'mac'
    linux = 'linux'


BROWSER_CMDS = {
    OSEnum.windows: {
        'chrome': [
            'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
            'C:/Program Files/Google/Chrome/Application/chrome.exe',
            os.getenv('LOCALAPPDATA', '') + r"/Google/Chrome/Application/chrome.exe",
        ]
    },
    OSEnum.mac: {
        'chrome': ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
    },
    OSEnum.linux: {'chrome': ['google-chrome']},
}


def windows_mac_or_linux() -> OSEnum:
    if sys.platform.startswith("win"):
        return OSEnum.windows
    elif sys.platform.startswith("darwin"):
        return OSEnum.mac
    else:
        return OSEnum.linux


class URLs:
    create_browser_bots = reverse('CreateBrowserBotsSession')


WEBSOCKET_COMPLETED_MESSAGE = b'closed_by_browser_launcher'
WEBSOCKET_1000 = 1000


class OtreeWebSocketClient(WebSocketClient):
    def __init__(self, *args, session_size, **kwargs):
        self.session_size = session_size
        self.seen_participant_codes = set()
        self.participants_finished = 0
        super().__init__(*args, **kwargs)

    def received_message(self, message):
        '''
        This is called automatically when the client receives a message
        '''
        code = json.loads(message)['participant_code']
        if code not in self.seen_participant_codes:
            self.seen_participant_codes.add(code)
            self.participants_finished += 1
            if self.participants_finished == self.session_size:
                self.close(reason=WEBSOCKET_COMPLETED_MESSAGE, code=WEBSOCKET_1000)

    def closed(self, code, reason=None):
        '''
        make sure the websocket closed properly,
        not because of server-side exception etc.
        '''
        # i used to check "reason", but for some reason it's always an empty string.
        if code != WEBSOCKET_1000:
            logger.error(
                f'Lost connection with server. '
                f'code: {code}, reason: "{reason}".'
                'Check the oTree server logs for errors.'
            )
            # don't know why, but this is not actually exiting,
            # even though it's in the same process.
            # even putting a breakpoint here just gets skipped past.
            sys.exit(-1)


def run_websocket_client_until_finished(*, websocket_url, session_size) -> float:
    '''for easy patching'''
    bot_start_time = time.time()
    ws_client = OtreeWebSocketClient(websocket_url, session_size=session_size)
    ws_client.connect()
    ws_client.run_forever()
    return round(time.time() - bot_start_time, 1)


class Launcher:
    def __init__(self, *, session_config_name, server_url, num_participants):
        self.session_config_name = session_config_name
        self.server_url = server_url
        self.num_participants = num_participants

    def run(self):

        self.check_browser()
        self.set_urls()
        self.client = requests_session()
        self.client.headers.update({'otree-rest-key': REST_KEY})

        sessions_to_create = []

        session_config_name = self.session_config_name
        if session_config_name:
            if session_config_name not in SESSION_CONFIGS_DICT:
                msg = 'No session config named "{}"'.format(session_config_name)
                raise ValueError(msg)
            session_config_names = [session_config_name]

        else:
            # default to all session configs
            session_config_names = SESSION_CONFIGS_DICT.keys()

        self.max_name_length = max(
            len(config_name) for config_name in session_config_names
        )

        for session_config_name in session_config_names:
            session_config = SESSION_CONFIGS_DICT[session_config_name]
            num_bot_cases = session_config.get_num_bot_cases()
            for case_number in range(num_bot_cases):
                num_participants = (
                    self.num_participants or session_config['num_demo_participants']
                )
                sessions_to_create.append(
                    {
                        'session_config_name': session_config_name,
                        'num_participants': num_participants,
                        'case_number': case_number,
                    }
                )

        total_time_spent = 0
        # run in a separate loop, because we want to validate upfront
        # that the session configs are valid, etc,
        # rather than the command failing halfway through
        for session_to_create in sessions_to_create:
            total_time_spent += self.run_session(**session_to_create)

        sys.stdout.write('Total: {} seconds\n'.format(round(total_time_spent, 1)))

        # don't delete sessions -- it's too susceptible to race conditions
        # between sending the completion message and loading the last page
        # plus people want to preserve the data
        # just label these sessions clearly in the admin UI
        # and make it easy to delete manually

    def run_session(self, session_config_name, num_participants, case_number):
        self.close_existing_session()

        secret_code = get_admin_secret_code()
        browser_process = self.launch_browser(num_participants, secret_code)

        row_fmt = "{:<%d} {:>2} participants..." % (self.max_name_length + 1)
        sys.stdout.write(row_fmt.format(session_config_name, num_participants))

        session_code = self.create_bb_session(
            session_config_name=session_config_name,
            num_participants=num_participants,
            case_number=case_number,
        )

        time_spent = self.websocket_listen(session_code, num_participants)
        sys.stdout.write('...finished in {} seconds\n'.format(time_spent))

        # TODO:
        # - if Chrome/FF is already running when the browser is launched,
        # this does nothing.
        # also, they report a crash (in Firefox it blocks the app from
        # starting again), in Chrome it's just a side notice
        browser_process.terminate()
        return time_spent

    def websocket_listen(self, session_code, num_participants) -> float:
        # seems that urljoin doesn't work with ws:// urls
        # so do the ws replace after URLjoin
        websocket_url = urljoin(
            self.server_url, channel_utils.browser_bots_launcher_path(session_code)
        )
        websocket_url = websocket_url.replace('http://', 'ws://').replace(
            'https://', 'wss://'
        )

        return run_websocket_client_until_finished(
            websocket_url=websocket_url, session_size=num_participants
        )

    def set_urls(self):
        # SERVER URL
        server_url = self.server_url
        # if it doesn't start with http:// or https://,
        # assume http://
        if not server_url.startswith('http'):
            server_url = 'http://' + server_url
        self.server_url = server_url

    def post(self, url, json=None):
        json = json or {}
        return self.client.post(urljoin(self.server_url, url), json=json)

    def create_bb_session(self, **payload):
        resp = self.post(URLs.create_browser_bots, json=payload)
        assert resp.ok, 'Failed to create session. Check the server logs.'
        session_code = resp.text
        return session_code

    def check_browser(self):
        platform = windows_mac_or_linux()

        custom_browser_cmd = getattr(settings, 'BROWSER_COMMAND', None)
        if custom_browser_cmd:
            self.browser_cmds = [custom_browser_cmd]
        else:
            # right now hardcoded to Chrome unless settings.BROWSER_COMMAND set
            self.browser_cmds = BROWSER_CMDS[platform]['chrome']

        first_browser_type = self.browser_cmds[0].lower()
        # check if browser is running
        if 'chrome' in first_browser_type:
            browser_type = 'Chrome'
        elif 'firefox' in first_browser_type:
            browser_type = 'Firefox'
        else:
            return

        if platform == OSEnum.windows:
            process_list_args = ['tasklist']
        else:
            process_list_args = ['ps', 'axw']
        ps_output = check_output(process_list_args).decode(
            sys.stdout.encoding, 'ignore'
        )
        is_running = browser_type.lower() in ps_output.lower()

        if is_running:
            sys.stdout.write(
                'WARNING: it looks like {browser} is already running. '
                'You should quit {browser} before running '
                'this command.\n'.format(browser=browser_type)
            )

    def close_existing_session(self):
        # make sure room is closed
        resp = self.post(reverse('CloseBrowserBotsSession'))
        if not resp.ok:
            msg = (
                'Request to close existing browser bots session failed. '
                'Response: {} {}'.format(repr(resp), resp.text)
            )
            raise AssertionError(msg)

    def launch_browser(self, num_participants, secret_code):
        wait_room_url = urljoin(self.server_url, reverse('BrowserBotStartLink'),)

        for browser_cmd in self.browser_cmds:
            args = [browser_cmd]
            if os.environ.get('BROWSER_BOTS_USE_HEADLESS'):
                args.append('--headless')
                # needed in windows
                args.append('--disable-gpu')

                # for some reason --screenshot OR --remote-debugging-port is necessary to get my JS to execute?!?
                # NO idea why. --remote-debugging-port gets me further than --screenshot, which gets stuck
                # on skip_lookahead
                # --remote-debugging-port=9222 works also
                args.append('--remote-debugging-port=9222')

            for i in range(num_participants):
                args.append(wait_room_url)
            try:
                return Popen(args)
            except FileNotFoundError:
                pass
        msg = (
            'Could not find a browser at the following path(s):\n\n'
            '{}\n\n'
            'Note: in settings.py, you can set BROWSER_COMMAND '
            'to the path to your browser executable. '
            'Otherwise, oTree will try to launch Chrome from its usual path.'
        ).format('\n'.join(self.browser_cmds))
        # we should show the original exception, because it might have
        # valuable info about why the browser didn't launch,
        # not raise from None.
        raise FileNotFoundError(msg)
