from typing import List
import logging
from collections import OrderedDict, defaultdict
from unittest import mock


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
from otree.constants_internal import AUTO_NAME_BOTS_EXPORT_FOLDER
from otree.models_concrete import ParticipantToPlayerLookup
from otree.models import Session, Participant

logger = logging.getLogger(__name__)


class SessionBotRunner:
    def __init__(self, bots: List[ParticipantBot]):
        self.bots = OrderedDict()

        for bot in bots:
            self.bots[bot.participant_id] = bot

    def play(self):
        '''round-robin'''
        self.open_start_urls()
        loops_without_progress = 0
        while True:
            if len(self.bots) == 0:
                return
            # bots got stuck if there's 2 wait pages in a row
            if loops_without_progress > 10:
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

    def open_start_urls(self):
        for bot in self.bots.values():
            bot.open_start_url()


def make_bots(*, session_pk, case_number, use_browser_bots) -> List[ParticipantBot]:
    update_kwargs = {'_is_bot': True}
    if use_browser_bots:
        update_kwargs['is_browser_bot'] = True

    Participant.objects.filter(session_id=session_pk).update(**update_kwargs)
    bots = []

    # can't use .distinct('player_pk') because it only works on Postgres
    # this implicitly orders by round also
    lookups = ParticipantToPlayerLookup.objects.filter(
        session_pk=session_pk).order_by('page_index')

    seen_players = set()
    lookups_per_participant = defaultdict(list)
    for lookup in lookups:
        player_identifier = (lookup.app_name, lookup.player_pk)
        if not player_identifier in seen_players:
            lookups_per_participant[lookup.participant_code].append(lookup)
            seen_players.add(player_identifier)

    for participant_code, lookups in lookups_per_participant.items():
        bot = ParticipantBot(lookups=lookups, case_number=case_number)
        bots.append(bot)

    return bots


def run_bots(session: Session, case_number=None):
    bot_list = make_bots(
        session_pk=session.pk, case_number=case_number, use_browser_bots=False
    )
    runner = SessionBotRunner(bots=bot_list)
    runner.play()


# function name needs to start with "test" for pytest to discover it
# in this module
@pytest.mark.django_db(transaction=True)
def test_all_bots_for_session_config(
        session_config_name, num_participants, *, run_export):
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
        )

        run_bots(session, case_number=case_number)
        logger.info('Bots completed session')
    if run_export:
        # bug: if the user tests multiple session configs,
        # the data will only be exported for the last session config.
        # this is because the DB is cleared after each test case.
        # fix later if this becomes high priority
        export_path = pytest.config.option.export_path

        now = datetime.datetime.now()

        if export_path == AUTO_NAME_BOTS_EXPORT_FOLDER:
            # oTree convention to prefix __temp all temp folders.
            export_path = now.strftime('__temp_bots_%b%d_%Hh%Mm%S.%f')[:-5] + 's'

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
    # --tb=short is to show short tracebacks. I think this is
    # more expected and less verbose.
    # With the default pytest long tracebacks,
    # often the code that gets printed is in otree-core, which is not relevant.
    # also, this is better than using --tb=native, which loses line breaks
    # when a unicode char is contained in the output, and also doesn't get
    # color coded with colorama, the way short tracebacks do.
    argv = [
        this_module.__file__,
        '-s',
        '--tb', 'short'
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
    otree.common_internal.patch_migrations_module()
    return pytest.main(argv)
