#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from threading import Thread
from huey.contrib.djhuey import HUEY
import six
import requests
from queue import Queue
from django.core.management.base import BaseCommand
from otree.models import Participant
from otree.session import create_session
from django.core.management import call_command
from six.moves import urllib
import webbrowser
import redis

from django.conf import settings
from subprocess import call, Popen, PIPE, STDOUT, CalledProcessError, DEVNULL

FIREFOX_PATH_MSWIN = "C:/Program Files (x86)/Mozilla Firefox/firefox.exe"
CHROME_PATH_MSWIN = 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe'

class Command(BaseCommand):
    help = "oTree: Run browser bots."

    def add_arguments(self, parser):
        parser.add_argument(
            'session_config_name', type=six.u, help="The session config name")
        parser.add_argument(
            '--base_url', action='store', type=str, dest='base_url',
            default='http://127.0.0.1:8000',
            help='Base URL')

    def handle(self, *args, **options):
        session_config_name = options["session_config_name"]
        base_url = options['base_url']

        # need to set USE_BROWSER_BOTS = True
        # in settings.py, because the server process needs
        # it set to True also
        # TODO: maybe pass it through CLI arg, or env var
        if not settings.USE_BROWSER_BOTS:
            raise Exception(
                'You need to set USE_BROWSER_BOTS = True '
                'in settings.py, before running this command.'
            )

        try:
            resp = requests.get(base_url)
            assert resp.ok
        except:
            raise Exception(
                'Could not connect to server at {}.'
                'Before running this command, '
                'you need to run the server.'.format(
                    base_url)
            )


        session_sizes = [6, 12, 24, 36]

        for num_participants in session_sizes:

            try:
                start_url = urllib.parse.urljoin(base_url, '/room/browser_bots/')
                args = [FIREFOX_PATH_MSWIN]
                for i in range(num_participants):
                    args.append(start_url)

                browser_process = Popen(args)

                bots_finished = redis.StrictRedis(db=15)

                print('Creating a session with {} participants'.format(num_participants))
                session = create_session(
                    session_config_name=session_config_name,
                    num_participants=num_participants,
                    room_name='browser_bots'
                )

                bot_start_time = time.time()

                #browser_process.wait()
                participants_finished = 0
                while True:
                    if bots_finished.lpop(session.code):
                        participants_finished += 1
                        if participants_finished == num_participants:
                            break
                    else:
                        time.sleep(0.1)


                #for i in range(num_participants):
                #    bots_finished.blpop(session.code)
                #    print('{} participants finished'.format(i + 1))

                print('{}: {} bots finished in {} seconds'.format(
                    session_config_name,
                    num_participants,
                    round(time.time() - bot_start_time, 2),
                ))

                # .terminate() is not doing anything for me on Firefox
                browser_process.kill()
            except:
                session.delete()
                raise

