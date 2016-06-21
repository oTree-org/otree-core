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
import logging
from django.conf import settings
from requests.packages.urllib3.exceptions import NewConnectionError


class Command(BaseCommand):
    help = "oTree: Create a session."

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

        settings.USE_BROWSER_BOTS = True
        session = create_session(
            session_config_name=session_config_name,
            num_participants=num_participants)

        # change to runprodserver
        t = Thread(target=call_command, args=['runserver', '--noreload'], daemon=True)
        t.start()

        SERVER_STARTUP_TIMEOUT = 20
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
            time.sleep(2)
        if not ping_ok:
            raise Exception(
                'Could not start server within {} seconds'.format(
                    SERVER_STARTUP_TIMEOUT)
            )

        participant_codes = Participant.objects.filter(
            session=session).values_list('code', flat=True)
        assert len(participant_codes) == num_participants

        start_urls = [urllib.parse.urljoin(base_url, 'InitializeParticipant/{}'.format(code))
                      for code in participant_codes]

        # hack: Logically this should be a boolean
        # but I need to mutate it inside the ListenFilter
        # so just used a list...maybe there is a smarter way
        all_bots_finished = Queue()

        class ListenFilter(logging.Filter):
            def filter(self, record):
                msg = record.getMessage()
                if session.code in msg and 'all browser bots finished' in msg:
                    all_bots_finished.put(True)

        logger = logging.getLogger('otree.test.browser_bots')
        filter = ListenFilter()
        logger.addFilter(filter)

        webbrowser.open_new_tab(base_url)
        time.sleep(3)

        for url in start_urls:
            webbrowser.open_new_tab(url)
        bot_start_time = time.time()

        # queue blocks until an item is available
        all_bots_finished.get()
        print('{}: {} bots finished in {} seconds'.format(
            session_config_name,
            num_participants,
            time.time() - bot_start_time,
        ))

        logger.removeFilter(filter)
        session.delete()





