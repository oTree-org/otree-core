#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import time
import logging
import six
import requests
from django.core.management.base import BaseCommand
from six.moves import urllib
from django.core.urlresolvers import reverse
from django.conf import settings
import subprocess
from otree.room import ROOM_DICT
from otree.session import SESSION_CONFIGS_DICT
from ws4py.client.threadedclient import WebSocketClient

# how do i import this properly?
urljoin = urllib.parse.urljoin

BROWSER_CMDS = {
    'windows': {
        'chrome': 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',  # noqa
        'firefox': "C:/Program Files (x86)/Mozilla Firefox/firefox.exe",
    },
    'mac': {
        'chrome': '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',  # noqa
        'firefox': None
    },
    'linux': {
        'firefox': 'firefox',
        'chrome': 'google-chrome',
    }
}

if sys.platform.startswith("win"):
    platform = 'windows'
elif sys.platform.startswith("darwin"):
    platform = 'mac'
else:
    platform = 'linux'

CHROME_CMD = BROWSER_CMDS[platform]['chrome']

DEFAULT_ROOM_NAME = 'browser_bots'

ROOM_FLAG = '--room'
NUM_PARTICIPANTS_FLAG = '--num-participants'
SERVER_URL_FLAG = '--server-url'


RUNSERVER_WARNING = '''
You are using "otree runserver". In order to use browser bots,
you should run a multiprocess server (e.g. "otree webandworkers").
'''

SQLITE_WARNING = '''
WARNING: Your server is running using SQLite.
Browser bots may not run properly.
We recommend using to Postgres or MySQL etc.
'''

AUTH_FAILURE_MESSAGE = """
Could not login to the server using your ADMIN_USERNAME
and ADMIN_PASSWORD from settings.py. If you are testing
browser bots on a remote server, make sure the username
and password on your local oTree installation match that
on the server.
"""


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


class Command(BaseCommand):
    help = "oTree: Run browser bots."

    def add_arguments(self, parser):
        parser.add_argument(
            'session_config_name', nargs='*',
            help='If omitted, all sessions in SESSION_CONFIGS are run'
        )
        parser.add_argument(
            SERVER_URL_FLAG, action='store', type=str, dest='server_url',
            default='http://127.0.0.1:8000',
            help="Server's root URL")
        ahelp = (
            'Numbers of participants. '
            'Defaults to minimum for the session config.'
        )
        parser.add_argument(
            '-n', NUM_PARTICIPANTS_FLAG, type=int, nargs='*',
            help=ahelp)
        ahelp = (
            'Room to create the session in (see settings.ROOMS).'
            'Room must NOT have a participant_label_file.'
        )
        parser.add_argument(
            ROOM_FLAG, action='store', type=str,
            default=DEFAULT_ROOM_NAME,
            help=ahelp)

    def websocket_listen(self, session_code, num_participants):
        # seems that urljoin doesn't work with ws:// urls
        # so do the ws replace after URLjoin
        websocket_url = urljoin(
            self.server_url,
            '/browser_bots_client/{}/'.format(session_code)
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
        return self.client.post(url, data)

    def close_room(self):
        # make sure room is closed
        resp = self.client.get(
            urljoin(self.server_url,
                    reverse('CloseRoom', args=[self.room_name])))
        assert resp.ok

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
        server_check = resp.json()

        if server_check['runserver']:
            print(RUNSERVER_WARNING)
        if server_check['sqlite']:
            print(SQLITE_WARNING)

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
                'you need to run the server (see {} flag).'.format(
                    self.server_url,
                    SERVER_URL_FLAG
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

    def create_session(self, session_config_name, num_participants):

        resp = self.post(
            self.create_session_url,
            data={
                'session_config_name': session_config_name,
                'num_participants': num_participants,
            }
        )
        assert resp.ok, 'Failed to create session'
        session_code = resp.content.decode('utf-8')
        return session_code

    def set_browser_cmd(self):
        self.browser_cmd = getattr(
            settings, 'BROWSER_COMMAND', CHROME_CMD
        )

        if 'chrome' in self.browser_cmd.lower():
            # FIXME: this is slow on Mac (maybe Linux too)
            # maybe use ps|grep instead
            '''
            chrome_seen = False
            for proc in psutil.process_iter():
                if 'chrome' in proc.name().lower():
                    chrome_seen = True
            if chrome_seen:
                print(
                    'WARNING: it looks like Chrome is already running. '
                    'You should quit Chrome before running this command.'
                )
            '''
            print(
                'Make sure to close all Chrome windows before launching '
                'This command.'
                'For best results, use Chrome with no addons or ad-blocker. '
                'e.g. create a new Chrome profile.'
            )

    def set_room_name(self):
        room_name = self.options['room']
        if room_name not in ROOM_DICT:
            raise ValueError(
                'No room named {} found in settings.ROOMS. '
                'You must either create a room named {}, '
                'or pass a {} argument with the name of your room. '
                'Note: room must NOT have a participant_label_file.'.format(
                    room_name,
                    room_name,
                    ROOM_FLAG,
                )
            )

        self.room_name = room_name

    def launch_browser(self, num_participants):
        wait_room_url = urljoin(
            self.server_url,
            reverse('AssignVisitorToRoom', args=[self.room_name])
        )

        args = [self.browser_cmd]
        for i in range(num_participants):
            args.append(wait_room_url)

        try:
            return subprocess.Popen(args)
        except Exception as exception:
            msg = (
                'Could not launch browser. '
                'Check your settings.BROWSER_COMMAND. {}'
            )
            ExceptionClass = type(exception)
            six.reraise(
                ExceptionClass,
                ExceptionClass(msg.format(exception)),
                sys.exc_info()[2])

    def handle(self, *args, **options):
        self.options = options

        self.set_room_name()
        self.set_browser_cmd()
        self.set_urls()
        self.client = requests.session()
        self.ping_server()
        self.server_configuration_check()

        sessions_to_create = []

        session_config_names = options["session_config_name"]
        if session_config_names:
            for session_config_name in session_config_names:
                if session_config_name not in SESSION_CONFIGS_DICT:
                    raise ValueError(
                        'No session config named "{}"'.format(
                            session_config_name)
                    )
        else:
            # default to all session configs
            session_config_names = SESSION_CONFIGS_DICT.keys()

        self.max_name_length = max(
            len(config_name) for config_name in session_config_names
        )

        for session_config_name in session_config_names:
            session_config = SESSION_CONFIGS_DICT[session_config_name]
            if options['num_participants']:
                session_sizes_for_this_config = options['num_participants']
            else:
                session_sizes_for_this_config = [
                    session_config['num_demo_participants']]

            for num_participants in session_sizes_for_this_config:
                sessions_to_create.append({
                    'session_config_name': session_config_name,
                    'num_participants': num_participants,
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

    def run_session(self, session_config_name, num_participants):
        self.close_room()

        browser_process = self.launch_browser(num_participants)

        row_fmt = "{:<%d} {:>2} participants..." % (self.max_name_length + 1)
        print(row_fmt.format(session_config_name, num_participants), end='')

        session_code = self.create_session(
            session_config_name, num_participants)

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
