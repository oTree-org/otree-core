import logging
import subprocess
import sys
import time
import os
import requests
from django.conf import settings
from django.urls import reverse
from urllib.parse import urljoin
import otree.channels.utils as channel_utils

from otree.session import SESSION_CONFIGS_DICT
from ws4py.client.threadedclient import WebSocketClient

AUTH_FAILURE_MESSAGE = """
Could not login to the server using your ADMIN_USERNAME
and ADMIN_PASSWORD from settings.py. If you are testing
browser bots on a remote server, make sure the username
and password on your local oTree installation match that
on the server.
"""


BROWSER_CMDS = {
    'windows': {
        'chrome': [
            'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
            'C:/Program Files/Google/Chrome/Application/chrome.exe',
            os.getenv('LOCALAPPDATA', '') + r"\Google\Chrome\Application\chrome.exe",
            ],
    },
    'mac': {
        'chrome': ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'],
    },
    'linux': {
        'chrome': ['google-chrome'],
    }
}

def windows_mac_or_linux():
    if sys.platform.startswith("win"):
        platform = 'windows'
    elif sys.platform.startswith("darwin"):
        platform = 'mac'
    else:
        platform = 'linux'
    return platform


class OtreeWebSocketClient(WebSocketClient):

    def __init__(self, *args, **kwargs):
        self.session_size = kwargs.pop('session_size')
        self.seen_participant_codes = set()
        self.participants_finished = 0
        super(OtreeWebSocketClient, self).__init__(*args, **kwargs)

    def received_message(self, message):
        code = message
        if code not in self.seen_participant_codes:
            self.seen_participant_codes.add(code)
            self.participants_finished += 1
            if self.participants_finished == self.session_size:
                self.close(reason='success')


class Launcher:

    def __init__(self, options):
        self.options = options

    def run(self):
        options = self.options

        self.check_browser()
        self.set_urls()
        self.client = requests.session()
        self.ping_server()
        self.server_configuration_check()

        sessions_to_create = []

        if options["session_config_name"]:
            session_config_name = options["session_config_name"]
            if session_config_name not in SESSION_CONFIGS_DICT:
                raise ValueError(
                    'No session config named "{}"'.format(
                        session_config_name)
                )
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
                num_participants = (options.get('num_participants') or
                                    session_config['num_demo_participants'])
                sessions_to_create.append({
                    'session_config_name': session_config_name,
                    'num_participants': num_participants,
                    'case_number': case_number,
                })

        total_time_spent = 0
        # run in a separate loop, because we want to validate upfront
        # that the session configs are valid, etc,
        # rather than the command failing halfway through
        for session_to_create in sessions_to_create:
            total_time_spent += self.run_session(**session_to_create)

        print('Total: {} seconds'.format(
            round(total_time_spent, 1)
        ))

        # don't delete sessions -- it's too susceptible to race conditions
        # between sending the completion message and loading the last page
        # plus people want to preserve the data
        # just label these sessions clearly in the admin UI
        # and make it easy to delete manually

    def run_session(
            self, session_config_name, num_participants, case_number):
        self.close_existing_session()

        browser_process = self.launch_browser(num_participants)

        row_fmt = "{:<%d} {:>2} participants..." % (self.max_name_length + 1)
        print(row_fmt.format(session_config_name, num_participants), end='')

        session_code = self.create_session(
            session_config_name, num_participants, case_number)

        bot_start_time = time.time()

        self.websocket_listen(session_code, num_participants)

        time_spent = round(time.time() - bot_start_time, 1)
        print('...finished in {} seconds'.format(time_spent))

        # TODO:
        # - if Chrome/FF is already running when the browser is launched,
        # this does nothing.
        # also, they report a crash (in Firefox it blocks the app from
        # starting again), in Chrome it's just a side notice
        browser_process.terminate()
        return time_spent

    def websocket_listen(self, session_code, num_participants):
        # seems that urljoin doesn't work with ws:// urls
        # so do the ws replace after URLjoin
        websocket_url = urljoin(
            self.server_url,
            channel_utils.browser_bots_launcher_path(session_code)
        )
        websocket_url = websocket_url.replace(
            'http://', 'ws://').replace('https://', 'wss://')

        ws_client = OtreeWebSocketClient(
            websocket_url,
            session_size=num_participants,
        )
        ws_client.connect()
        ws_client.run_forever()

    def set_urls(self):
        # SERVER URL
        server_url = self.options['server_url']
        # if it doesn't start with http:// or https://,
        # assume http://
        if not server_url.startswith('http'):
            server_url = 'http://' + server_url
        self.server_url = server_url

        # CREATE_SESSION URL
        self.create_session_url = urljoin(
            server_url,
            reverse('CreateBrowserBotsSession')
        )

        # LOGIN URL
        # TODO: use reverse? reverse('django.contrib.auth.views.login')
        self.login_url = urljoin(server_url, '/accounts/login/')

    def post(self, url, data=None):
        data = data or {}
        data.update({'csrfmiddlewaretoken': self.client.cookies['csrftoken']})
        # need to set the referer for CSRF protection to work when using HTTPS
        return self.client.post(url, data, headers={'referer': url})

    def server_configuration_check(self):
        # .get just returns server readiness info
        # try to get this page without logging in
        # we don't want to login if it isn't necessary, because maybe
        # settings.ADMIN_PASSWORD is empty, and therefore no user account
        # exists.
        resp = self.client.get(self.create_session_url)

        # if AUTH_LEVEL is set on remote server, then this will redirect
        # to a login page
        login_url = self.login_url
        if login_url in resp.url:
            # login
            resp = self.post(
                login_url,
                data={
                    'username': settings.ADMIN_USERNAME,
                    'password': settings.ADMIN_PASSWORD,
                },
            )

            if login_url in resp.url:
                raise Exception(AUTH_FAILURE_MESSAGE)

            # get it again, we are logged in now
            resp = self.client.get(self.create_session_url)
        server_check = resp.json()  # noqa

        # no need to warn about these for now
        # if server_check['runserver']:
        #     print(RUNSERVER_WARNING)
        # if server_check['sqlite']:
        #     print(SQLITE_WARNING)

    def ping_server(self):

        logging.getLogger("requests").setLevel(logging.WARNING)

        try:
            # open this just to populate CSRF cookie
            # (because login page contains a form)
            resp = self.client.get(self.login_url)

        except:
            raise Exception(
                'Could not connect to server at {}.'
                'Before running this command, '
                'you need to run the server (see --server-url flag).'.format(
                    self.server_url,
                )
            )
        if not resp.ok:
            raise Exception(
                'Could not open page at {}.'
                '(HTTP status code: {})'.format(
                    self.login_url,
                    resp.status_code,
                )
            )

    def create_session(
            self, session_config_name, num_participants, case_number
            ):

        resp = self.post(
            self.create_session_url,
            data={
                'session_config_name': session_config_name,
                'num_participants': num_participants,
                'case_number': case_number,
            }
        )
        assert resp.ok, 'Failed to create session. Check the server logs.'
        session_code = resp.content.decode('utf-8')
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

        if windows_mac_or_linux() == 'windows':
            process_list_args = ['tasklist']
        else:
            process_list_args = ['ps', 'axw']
        ps_output = subprocess.check_output(process_list_args).decode('utf-8')
        is_running = browser_type.lower() in ps_output.lower()

        if is_running:
            print(
                'WARNING: it looks like {browser} is already running. '
                'You should quit {browser} before running '
                'this command.'.format(browser=browser_type)
            )

    def close_existing_session(self):
        # make sure room is closed
        resp = self.post(
            urljoin(self.server_url, reverse('CloseBrowserBotsSession')))
        if not resp.ok:
            raise AssertionError(
                'Request to close existing browser bots session failed. '
                'Response: {} {}'.format(repr(resp), resp.text)
            )

    def launch_browser(self, num_participants):
        wait_room_url = urljoin(
            self.server_url,
            reverse('BrowserBotStartLink')
        )

        for browser_cmd in self.browser_cmds:
            args = [browser_cmd]
            for i in range(num_participants):
                args.append(wait_room_url)
            try:
                return subprocess.Popen(args)
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