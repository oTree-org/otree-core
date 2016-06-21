#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from threading import Thread
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

class Command(BaseCommand):
    help = "oTree: Run browser bots."

    def add_arguments(self, parser):
        parser.add_argument(
            'session_config_name', type=six.u, help="The session config name")
        parser.add_argument(
            'num_participants', type=int,
            help="Number of participants for the created session")
        parser.add_argument(
            '--base_url', action='store', type=str, dest='base_url',
            default='http://127.0.0.1:8000',
            help='Base URL')

    def handle(self, *args, **options):
        session_config_name = options["session_config_name"]
        num_participants = options['num_participants']
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
        session = create_session(
            session_config_name=session_config_name,
            num_participants=num_participants)


        # TODO: change to runprodserver
        #t = Thread(
        #    target=call_command,
        #    #args=['runserver', '--noreload'],
        #    args=['webandworkers', '--addr=127.0.0.1'],
        #    #daemon=True
        #)
        #t.start()

        SERVER_STARTUP_TIMEOUT = 5
        start_time = time.time()
        ping_ok = False
        while time.time() - start_time < SERVER_STARTUP_TIMEOUT:
            try:
                resp = requests.get(base_url)
                if resp.ok:
                    ping_ok = True
                    break
            except:
                # raises various errors: ConnectionRefusedError, NewConnectionError,
                # etc.
                pass
            time.sleep(1)
        if not ping_ok:
            raise Exception(
                'Could not connect to server at {} within {} seconds. '
                'Before running this command, you need to run the server. '.format(
                    base_url,
                    SERVER_STARTUP_TIMEOUT)
            )

        start_urls = [urllib.parse.urljoin(base_url, p._start_url())
                      for p in session.get_participants()]


        # hack: open a tab then sleep a few seconds
        # on Firefox, this seems like a way to get each URL
        # being opened in tabs rather than windows.
        # (even if i use open_new_tab)
        webbrowser.open_new_tab(base_url)
        time.sleep(3)

        bot_start_time = time.time()
        for url in start_urls:
            webbrowser.open_new_tab(url)

        # queue blocks until an item is available
        bots_finished = redis.StrictRedis(db=15)
        for i in range(num_participants):
            bots_finished.blpop(session.code)

        print('{}: {} bots finished in {} seconds'.format(
            session_config_name,
            num_participants,
            round(time.time() - bot_start_time, 2),
        ))

        session.delete()





