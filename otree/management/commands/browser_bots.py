#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import time
import six
import requests
from django.core.management.base import BaseCommand
from otree.session import create_session
from six.moves import urllib
import redis
from django.core.urlresolvers import reverse
from django.conf import settings
from subprocess import Popen
from otree.room import ROOM_DICT
from otree.session import SESSION_CONFIGS_DICT, get_lcm

FIREFOX_PATH_MSWIN = "C:/Program Files (x86)/Mozilla Firefox/firefox.exe"
CHROME_PATH_MSWIN = (
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe'
)
DEFAULT_ROOM_NAME = 'browser_bots'

ROOM_FLAG = '--room'
NUM_PARTICIPANTS_FLAG = '--num_participants'
BASE_URL_FLAG = '--base_url'


class Command(BaseCommand):
    help = "oTree: Run browser bots."

    def add_arguments(self, parser):
        parser.add_argument(
            'session_config_name', type=six.u, help="The session config name")
        parser.add_argument(
            BASE_URL_FLAG, action='store', type=str, dest='base_url',
            default='http://127.0.0.1:8000',
            help='Base URL')
        ahelp = (
            'Numbers of participants. Examples: "12" or "4,12,18".'
            'Defaults to minimum for this session config.'
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
        session_config_name = options["session_config_name"]
        base_url = options['base_url']
        num_participants = options['num_participants']
        room_name = options['room']

        browser_path = getattr(
            settings, 'BROWSER_PATH', FIREFOX_PATH_MSWIN
        )

        session_config = SESSION_CONFIGS_DICT[session_config_name]

        if num_participants is not None:
            session_sizes = [int(n) for n in num_participants.split(',')]
        else:
            session_sizes = [get_lcm(session_config)]

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

        start_url = urllib.parse.urljoin(
            base_url,
            reverse('assign_visitor_to_room', args=[room_name])
        )

        try:
            resp = requests.get(start_url)
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

        for num_participants in session_sizes:
            args = [browser_path]
            for i in range(num_participants):
                args.append(start_url)

            try:
                browser_process = Popen(args)
            except Exception as exception:
                msg = (
                    'Could not launch browser. '
                    'Check your settings.BROWSER_PATH. {}'
                )

                six.reraise(
                    type(exception),
                    type(exception)(msg.format(exception)),
                    sys.exc_info()[2])

            bot_completion = redis.StrictRedis(
                host=settings.REDIS_HOSTNAME,
                port=settings.REDIS_PORT,
                # arbitrarily chosen DB name
                db=15
            )


            print(
                '{}, {} participants...'.format(
                    session_config_name,
                    num_participants),
                end=''
            )

            session = create_session(
                session_config_name=session_config_name,
                num_participants=num_participants,
                room_name='browser_bots',
                use_browser_bots=True
            )

            try:
                bot_start_time = time.time()

                participants_finished = 0
                while True:
                    if bot_completion.lpop(session.code):
                        participants_finished += 1
                        if participants_finished == num_participants:
                            break
                    else:
                        time.sleep(0.1)

                print('...finished in {} seconds'.format(
                    round(time.time() - bot_start_time, 1),
                ))

                # FIXME:
                # this doesn't work great:
                # - when I restart firefox, it sometimes launches in recovery
                #   mode, thinking that it crashed.
                # - if Firefox is already running when the browser is launched,
                # this does nothing.
                browser_process.terminate()

            finally:
                session.delete()
