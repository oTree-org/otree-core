import datetime
import logging
import os
from pathlib import Path
from typing import List


import otree.common
import otree.export
import otree.session
from otree import settings
from otree.common import get_bots_module, get_models_module
from otree.constants import AUTO_NAME_BOTS_EXPORT_FOLDER
from otree.database import values_flat, db
from otree.models import Session, Participant
from otree.session import SESSION_CONFIGS_DICT
from .bot import ParticipantBot

logger = logging.getLogger(__name__)


class SessionBotRunner:
    def __init__(self, bots: List[ParticipantBot]):
        self.bots = {}

        for bot in bots:
            self.bots[bot.participant_code] = bot

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
            for id in playable_ids:
                bot = self.bots[id]
                if bot.on_wait_page():
                    pass
                else:
                    try:
                        submission = bot.get_next_submit()
                    except StopIteration:
                        # this bot is finished
                        self.bots.pop(id)
                    else:
                        bot.submit(submission)
                    progress_made = True
                    # need to set this so that we only count *consecutive* unsuccessful loops
                    # see Manu's error on 2019-12-19.
                    loops_without_progress = 0
            if not progress_made:
                loops_without_progress += 1

    def open_start_urls(self):
        for bot in self.bots.values():
            bot.open_start_url()


def make_bots(*, session_pk, case_number, use_browser_bots) -> List[ParticipantBot]:
    update_kwargs = {Participant._is_bot: True}
    if use_browser_bots:
        update_kwargs[Participant.is_browser_bot] = True

    Participant.objects_filter(session_id=session_pk).update(update_kwargs)
    bots = []

    # can't use .distinct('player_pk') because it only works on Postgres
    # this implicitly orders by round also
    session = Session.objects_get(id=session_pk)

    participant_codes = values_flat(session.pp_set.order_by('id'), Participant.code)

    player_bots_dict = {pcode: [] for pcode in participant_codes}

    for app_name in session.config['app_sequence']:
        bots_module = get_bots_module(app_name)
        models_module = get_models_module(app_name)
        Player = models_module.Player
        players = (
            Player.objects_filter(session_id=session_pk)
            .join(Participant)
            .order_by('round_number')
            .with_entities(Player.id, Participant.code, Player.subsession_id)
        )
        for player_id, participant_code, subsession_id in players:
            player_bot = bots_module.PlayerBot(
                case_number=case_number,
                app_name=app_name,
                player_pk=player_id,
                subsession_pk=subsession_id,
                participant_code=participant_code,
                session_pk=session_pk,
            )
            player_bots_dict[participant_code].append(player_bot)

    executed_live_methods = set()

    for participant_code, player_bots in player_bots_dict.items():
        bot = ParticipantBot(
            participant_code,
            player_bots=player_bots,
            executed_live_methods=executed_live_methods,
        )
        bots.append(bot)

    return bots


def run_bots(session_id, case_number=None):
    session = Session.objects_get(id=session_id)
    bot_list = make_bots(
        session_pk=session.id, case_number=case_number, use_browser_bots=False
    )
    if session.get_room() is None:
        session.mock_exogenous_data()
        db.commit()
    runner = SessionBotRunner(bots=bot_list)
    runner.play()


def run_all_bots_for_session_config(session_config_name, num_participants, export_path):
    """
    this means all test cases are in 1 big test case.
    so if 1 fails, the others will not get run.
    """
    if session_config_name:
        session_config_names = [session_config_name]
    else:
        session_config_names = SESSION_CONFIGS_DICT.keys()

    for config_name in session_config_names:
        try:
            config = SESSION_CONFIGS_DICT[config_name]
        except KeyError:
            # important to alert the user, since people might be trying to enter app names.
            msg = f"No session config with name '{config_name}'."
            raise Exception(msg) from None

        num_bot_cases = config.get_num_bot_cases()
        for case_number in range(num_bot_cases):
            logger.info(
                "Creating '{}' session (test case {})".format(config_name, case_number)
            )

            session = otree.session.create_session(
                session_config_name=config_name,
                num_participants=(num_participants or config['num_demo_participants']),
            )
            session_id = session.id

            run_bots(session_id, case_number=case_number)

            logger.info('Bots completed session')
    if export_path:

        now = datetime.datetime.now()

        if export_path == AUTO_NAME_BOTS_EXPORT_FOLDER:
            # oTree convention to prefix __temp all temp folders.
            export_path = now.strftime('__temp_bots_%b%d_%Hh%Mm%S.%f')[:-5] + 's'

        os.makedirs(export_path, exist_ok=True)

        for app in settings.OTREE_APPS:
            model_module = otree.common.get_models_module(app)
            if model_module.Player.objects_exists():
                fpath = Path(export_path, "{}.csv".format(app))
                with fpath.open("w", newline='', encoding="utf8") as fp:
                    otree.export.export_app(app, fp)
        fpath = Path(export_path, "all_apps_wide.csv")
        with fpath.open("w", encoding="utf8") as fp:
            otree.export.export_wide(fp)

        logger.info('Exported CSV to folder "{}"'.format(export_path))
    else:
        logger.info(
            'Tip: Run this command with the --export flag'
            ' to save the data generated by bots.'
        )
