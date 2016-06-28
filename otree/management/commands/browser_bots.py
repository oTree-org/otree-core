#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import time
import logging
import six
import requests
from django.core.management.base import BaseCommand
from otree.session import create_session
from six.moves import urllib
from django.core.urlresolvers import reverse
from django.conf import settings
import subprocess
from otree.room import ROOM_DICT
from otree.session import SESSION_CONFIGS_DICT, get_lcm
from huey.contrib.djhuey import HUEY
import psutil

FIREFOX_CMDS = {
    'windows': "C:/Program Files (x86)/Mozilla Firefox/firefox.exe",
    'mac': None,
    'linux': 'firefox'
}

CHROME_CMDS = {
    'windows': 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'mac': '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    'linux': 'google-chrome',
}

if sys.platform.startswith("win"):
    platform = 'windows'
elif sys.platform.startswith("darwin"):
    platform = 'mac'
else:
    platform = 'linux'

CHROME_CMD = CHROME_CMDS[platform]

DEFAULT_ROOM_NAME = 'browser_bots'

ROOM_FLAG = '--room'
NUM_PARTICIPANTS_FLAG = '--num_participants'
BASE_URL_FLAG = '--base_url'


class Command(BaseCommand):
    help = "oTree: Run browser bots."

    def add_arguments(self, parser):
        parser.add_argument(
            'session_config_name', nargs='*',
            help='If omitted, all sessions in SESSION_CONFIGS are run'
        )
        parser.add_argument(
            BASE_URL_FLAG, action='store', type=str, dest='base_url',
            default='http://127.0.0.1:8000',
            help='Base URL')
        ahelp = (
            'Numbers of participants. Examples: "12" or "4,12,18".'
            'Defaults to minimum for the session config.'
        )
        parser.add_argument(
            '-n', NUM_PARTICIPANTS_FLAG, type=str,
            help=ahelp)
        ahelp = (
            'Room to create the session in (see settings.ROOMS).'
            'Room must NOT have a participant_label_file.'
        )
        parser.add_argument(
            ROOM_FLAG, action='store', type=str,
            default=DEFAULT_ROOM_NAME,
            help=ahelp)

    def handle(self, *args, **options):

        base_url = options['base_url']
        room_name = options['room']

        num_participants = options['num_participants']
        if num_participants is not None:
            self.session_sizes = [int(n) for n in num_participants.split(',')]
        else:
            self.session_sizes = None
        self.start_url = urllib.parse.urljoin(
            base_url,
            reverse('assign_visitor_to_room', args=[room_name])
        )

        session_config_names = options["session_config_name"]
        if not session_config_names:
            # default to all session configs
            session_config_names = SESSION_CONFIGS_DICT.keys()

        self.browser_cmd = getattr(
            settings, 'BROWSER_COMMAND', CHROME_CMD
        )

        if 'chrome' in self.browser_cmd.lower():
            chrome_seen = False
            for proc in psutil.process_iter():
                if 'chrome' in proc.name().lower():
                    chrome_seen = True
            if chrome_seen:
                print(
                    'WARNING: it looks like Chrome is already running. '
                    'You should quit Chrome before running this command.'
                )
            print(
                'For best results, use Chrome with no addons or ad-blocker. '
                'e.g. create a new Chrome profile.'
            )

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

        logging.getLogger("requests").setLevel(logging.WARNING)
        try:
            resp = requests.get(base_url)
            assert resp.ok
        except:
            raise Exception(
                'Could not open page at {}.'
                'Before running this command, '
                'you need to run the server (see {} flag).'.format(
                    base_url,
                    BASE_URL_FLAG
                )
            )

        self.max_name_length = max(
            len(config_name) for config_name in session_config_names
        )

        self.total_time_spent = 0

        for session_config_name in session_config_names:
            session_config = SESSION_CONFIGS_DICT[session_config_name]

            if self.session_sizes is None:
                size = get_lcm(session_config)
                # shouldn't just play 1 person because that doesn't test
                # the dynamics of multiplayer games with
                # players_per_group = None
                if size == 1:
                    size = 2
                session_sizes = [size]
            else:
                session_sizes = self.session_sizes

            for num_participants in session_sizes:
                self.run_session_config(session_config_name, num_participants)

        print('Total: {} seconds'.format(
            round(self.total_time_spent, 1)
        ))

    def run_session_config(self, session_config_name, num_participants):
        args = [self.browser_cmd]
        for i in range(num_participants):
            args.append(self.start_url)

        try:
            browser_process = subprocess.Popen(args)
        except Exception as exception:
            msg = (
                'Could not launch browser. '
                'Check your settings.BROWSER_COMMAND. {}'
            )

            six.reraise(
                type(exception),
                type(exception)(msg.format(exception)),
                sys.exc_info()[2])

        row_fmt = "{:<%d} {:>2} participants..." % (self.max_name_length + 1)
        print(row_fmt.format(session_config_name, num_participants), end='')

        session = create_session(
            session_config_name=session_config_name,
            num_participants=num_participants,
            room_name=self.room_name,
            use_browser_bots=True
        )

        try:
            bot_start_time = time.time()

            participants_finished = 0
            while True:
                if HUEY.storage.conn.lpop(session.code):
                    participants_finished += 1
                    if participants_finished == num_participants:
                        break
                else:
                    time.sleep(0.1)

            time_spent = round(time.time() - bot_start_time, 1)
            print('...finished in {} seconds'.format(time_spent))
            self.total_time_spent += time_spent

            # TODO:
            # - if Chrome/FF is already running when the browser is launched,
            # this does nothing.
            browser_process.terminate()

        finally:
            session.delete()
        return time_spent
