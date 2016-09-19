#!/usr/bin/env python
# -*- coding: utf-8 -*-


import logging
from collections import OrderedDict
import mock

from django.db.migrations.loader import MigrationLoader
from django.conf import settings
import pytest
import sys

import otree.session
import otree.common_internal

from .bot import ParticipantBot
import datetime
import os
import codecs
import otree.export

logger = logging.getLogger(__name__)


class SessionBotRunner(object):
    def __init__(self, bots, session_code):
        self.bots = OrderedDict()

        for bot in bots:
            self.bots[bot.participant.id] = bot

    def play_until_end(self):
        '''round-robin'''
        loops_without_progress = 0
        while True:
            if len(self.bots) == 0:
                print('Bots done!')
                return
            if loops_without_progress > 2:
                raise AssertionError('Bots got stuck')
            # store in a separate list so we don't mutate the iterable
            playable_ids = list(self.bots.keys())
            progress_made = False
            for pk in playable_ids:
                bot = self.bots[pk]
                if bot.on_wait_page():
                    pass
                else:
                    try:
                        submission = next(bot.submits_generator)
                    except StopIteration:
                        # this bot is finished
                        self.bots.pop(pk)
                        progress_made = True
                    else:
                        bot.submit(submission)
                        progress_made = True
            if not progress_made:
                loops_without_progress += 1


@pytest.mark.django_db(transaction=True)
def test_bots(session_config_name, num_participants, run_export):
    config_name = session_config_name
    session_config = otree.session.SESSION_CONFIGS_DICT[config_name]

    # num_bots is deprecated, because the old default of 12 or 6 was too
    # much, and it doesn't make sense to
    if num_participants is None:
        num_participants = session_config['num_demo_participants']

    num_bot_cases = session_config.get_num_bot_cases()
    for case_number in range(num_bot_cases):
        if num_bot_cases > 1:
            logger.info("Creating '{}' session (test case {})".format(
                config_name, case_number))
        else:
            logger.info("Creating '{}' session".format(config_name))

        session = otree.session.create_session(
            session_config_name=config_name,
            num_participants=num_participants,
            use_cli_bots=True,
            bot_case_number=case_number
        )
        bots = []

        for participant in session.get_participants():
            bot = ParticipantBot(participant)
            bots.append(bot)
            bot.open_start_url()

        bot_runner = SessionBotRunner(bots, session.code)
        bot_runner.play_until_end()
    if run_export:
        # bug: if the user tests multiple session configs,
        # the data will only be exported for the last session config.
        # this is because the DB is cleared after each test case.
        # fix later if this becomes high priority
        export_path = pytest.config.option.export_path

        now = datetime.datetime.now()

        if export_path == 'auto_name':
            export_path = now.strftime('_bots_%b%d_%Hh%Mm%S.%f')[:-5] + 's'

        if os.path.isdir(export_path):
            msg = "Directory '{}' already exists".format(export_path)
            raise IOError(msg)

        os.makedirs(export_path)

        for app in settings.INSTALLED_OTREE_APPS:
            model_module = otree.common_internal.get_models_module(app)
            if model_module.Player.objects.exists():
                fname = "{}.csv".format(app)
                fpath = os.path.join(export_path, fname)
                with codecs.open(fpath, "w", encoding="utf8") as fp:
                    otree.export.export_app(app, fp, file_extension='csv')

        logger.info('Exported CSV to folder "{}"'.format(export_path))


def run_pytests(**kwargs):

    session_config_name = kwargs['session_config_name']
    num_participants = kwargs['num_participants']
    verbosity = kwargs['verbosity']

    this_module = sys.modules[__name__]

    # '-s' is to see print output
    # --tb=native is to show native Python tracebacks. I think this is
    # more expected and less verbose. With the native tracebacks,
    # Often the code that gets printed is in otree-core, which is not relevant
    argv = [
        this_module.__file__,
        '-s',
        '--tb', 'native'
    ]
    if verbosity == 0:
        argv.append('--quiet')
    if verbosity == 2:
        argv.append('--verbose')

    if session_config_name:
        argv.extend(['--session_config_name', session_config_name])
    if num_participants:
        argv.extend(['--num_participants', num_participants])
    if kwargs['preserve_data']:
        argv.append('--preserve_data')
    if kwargs['export_path']:
        argv.extend(['--export_path', kwargs['export_path']])

    # same hack as in resetdb code
    # because this method uses the serializer
    # it breaks if the app has migrations but they aren't up to date
    with mock.patch.object(
            MigrationLoader,
            'migrations_module',
            return_value='migrations nonexistent hack'
    ):

        return pytest.main(argv)
