#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random
import six
from functools import reduce
from collections import OrderedDict
import sys
import itertools

from django.conf import settings
from django.db import transaction
from django.db.utils import OperationalError

from six.moves import range
from six.moves import zip
import schema

import otree.db.idmap
from otree import constants_internal
from otree.models.session import Session
from otree.models.participant import Participant
from otree.common_internal import (
    get_models_module, get_app_constants, validate_identifier,
    min_players_multiple,
    get_redis_conn
)
import otree.common_internal
from otree.common import RealWorldCurrency
from decimal import Decimal
from otree import deprecate
from otree.models_concrete import ParticipantLockModel
import otree.bots.browser

def gcd(a, b):
    """Return greatest common divisor using Euclid's Algorithm."""
    while b:
        a, b = b, a % b
    return a


def lcm(a, b):
    """Return lowest common multiple."""
    return a * b // gcd(a, b)


def lcmm(*args):
    """Return lcm of args."""
    return reduce(lcm, args)


def get_lcm(session_config):
    min_multiple_list = []
    for app_name in session_config['app_sequence']:
        app_constants = get_app_constants(app_name)
        # if players_per_group is None, 0, etc.
        min_multiple = min_players_multiple(
            app_constants.players_per_group)
        min_multiple_list.append(min_multiple)
    return lcmm(*min_multiple_list)


def validate_session_config(config):

    config_schema = schema.Schema({
        'name': str,
        'app_sequence': list,
        'participation_fee': object,
        'num_bots': int,
        'display_name': str,
        'real_world_currency_per_point': object,
        'num_demo_participants': int,
        'doc': str,
        object: object,
    })

    try:
        config = config_schema.validate(config)
    except schema.SchemaError as e:
        raise ValueError('settings.SESSION_CONFIGS: {}'.format(e))

    validate_identifier(
        config['name'],
        identifier_description='settings.SESSION_CONFIG name'
    )


    app_sequence = config['app_sequence']
    if len(app_sequence) != len(set(app_sequence)):
        msg = (
            'settings.SESSION_CONFIGS: '
            'app_sequence of "{}" '
            'must not contain duplicate elements. '
            'If you want multiple rounds, '
            'you should set Constants.num_rounds.')
        raise ValueError(msg.format(config['name']))

    if len(app_sequence) == 0:
        raise ValueError(
            'settings.SESSION_CONFIGS: Need at least one subsession.')


def augment_session_config(session_config):
    new_session_config = {'doc': ''}
    new_session_config.update(settings.SESSION_CONFIG_DEFAULTS)
    new_session_config.update(session_config)

    # look up new_session_config
    # 2015-05-14: why do we strip? the doc can have line breaks in the middle
    # anyways
    new_session_config['doc'] = new_session_config['doc'].strip()

    # TODO: fixed_pay is deprecated as of 2015-05-07,
    # in favor of participation_fee. make this required at some point.
    if (('participation_fee' not in new_session_config) and
            ('fixed_pay' in new_session_config)):
        deprecate.dwarning(
            '"fixed_pay" is deprecated; '
            'you should rename it to "participation_fee".'
        )
        new_session_config['participation_fee'] = (
            new_session_config['fixed_pay'])

    new_session_config['participation_fee'] = RealWorldCurrency(
        new_session_config['participation_fee'])

    # normalize to decimal so we can do multiplications, etc
    # quantize because the original value may be a float,
    # which when converted to Decimal may have some 'decimal junk'
    # like 0.010000000000000000208166817...
    new_session_config['real_world_currency_per_point'] = Decimal(
        new_session_config['real_world_currency_per_point']
    ).quantize(Decimal('0.00001'))

    validate_session_config(new_session_config)
    return new_session_config


def get_session_configs_dict():
    SESSION_CONFIGS_DICT = OrderedDict()
    for config in settings.SESSION_CONFIGS:
        SESSION_CONFIGS_DICT[config['name']] = augment_session_config(config)
    return SESSION_CONFIGS_DICT

SESSION_CONFIGS_DICT = get_session_configs_dict()


def app_labels_from_sessions(config_names):
    apps = set()
    for config_name in config_names:
        config = SESSION_CONFIGS_DICT[config_name]
        apps.update(config["app_sequence"])
    return apps



def create_session(
        session_config_name, label='', num_participants=None,
        _pre_create_id=None,
        room_name=None, for_mturk=False, use_cli_bots=False,
        is_demo=False, force_browser_bots=False,
        honor_browser_bots_config=False,
                   ):

    session = None
    use_browser_bots = False

    with transaction.atomic():
        # 2014-5-2: i could implement this by overriding the __init__ on the
        # Session model, but I don't really know how that works, and it seems to
        # be a bit discouraged: http://goo.gl/dEXZpv
        # 2014-9-22: preassign to groups for demo mode.

        otree.db.idmap.activate_cache()

        try:
            session_config = SESSION_CONFIGS_DICT[session_config_name]
        except KeyError:
            msg = 'Session config "{}" not found in settings.SESSION_CONFIGS.'
            raise ValueError(msg.format(session_config_name))

        if force_browser_bots:
            use_browser_bots = True
        elif (session_config.get('use_browser_bots') and
                  honor_browser_bots_config):
            use_browser_bots = True
        else:
            use_browser_bots = False


        session = Session.objects.create(
            config=session_config,
            label=label,
            _pre_create_id=_pre_create_id,
            _use_browser_bots=use_browser_bots,
            is_demo=is_demo
        )

        def bulk_create(model, descriptions):
            model.objects.bulk_create([
                model(session=session, **description)
                for description in descriptions])
            return model.objects.filter(session=session).order_by('pk')

        if num_participants is None:
            if is_demo:
                num_participants = session_config['num_demo_participants']
            elif use_cli_bots:
                num_participants = session_config['num_bots']

        # check that it divides evenly
        session_lcm = get_lcm(session_config)
        if num_participants % session_lcm:
            msg = (
                'Session Config {}: Number of participants ({}) does not divide '
                'evenly into group size ({})')
            raise ValueError(
                msg.format(session_config['name'], num_participants, session_lcm))

        if for_mturk:
            session.mturk_num_participants = (
                    num_participants /
                    settings.MTURK_NUM_PARTICIPANTS_MULT)

        start_order = list(range(num_participants))
        if session_config.get('random_start_order'):
            random.shuffle(start_order)


        participants = bulk_create(
            Participant,
            [{
                'id_in_session': id_in_session,
                'start_order': j,
                # check if id_in_session is in the bots ID list
                '_is_bot': use_cli_bots or use_browser_bots,
             }
             for id_in_session, j in enumerate(start_order, start=1)])

        ParticipantLockModel.objects.bulk_create([
            ParticipantLockModel(participant_code=participant.code)
            for participant in participants])

        try:
            for app_name in session_config['app_sequence']:

                models_module = get_models_module(app_name)
                app_constants = get_app_constants(app_name)

                round_numbers = list(range(1, app_constants.num_rounds + 1))

                subs = bulk_create(
                    models_module.Subsession,
                    [{'round_number': round_number}
                     for round_number in round_numbers])

                # Create players
                models_module.Player.objects.bulk_create([
                    models_module.Player(
                        session=session,
                        subsession=subsession,
                        round_number=round_number,
                        participant=participant)
                    for round_number, subsession in zip(round_numbers, subs)
                    for participant in participants])

            session._create_groups_and_initialize()

        # session.has_bots = any(p.is_bot ...)

        # handle case where DB has missing column or table
        # missing table: OperationalError: no such table: pg_subsession
        # missing column: OperationalError: table pg_player has no column
        # named contribution2
        except OperationalError as exception:
            exception_str = str(exception)
            if 'table' in exception_str:
                ExceptionClass = type(exception)
                six.reraise(
                    ExceptionClass,
                    ExceptionClass('{} - Try resetting the database.'.format(
                        exception_str)),
                    sys.exc_info()[2])
            raise

        session.build_participant_to_player_lookups()
        # automatically save all objects since the cache was activated:
        # Player, Group, Subsession, Participant, Session
        otree.db.idmap.save_objects()
        otree.db.idmap.deactivate_cache()

    if use_browser_bots:
        redis_conn = get_redis_conn()
        # what about clear_browser_bots? if session is created through
        # UI, when do we run that? it should be run when the session
        # is deleted
        print('{} participants, {}'.format(num_participants, session_config_name))
        try:
            otree.bots.browser.initialize_bots(redis_conn, session.code)
        except:
            session.delete()
            raise

    session.ready = True
    session.save()

    # this should happen after session.ready = True
    if room_name is not None:
        from otree.room import ROOM_DICT
        room = ROOM_DICT[room_name]
        room.session = session


    return session


default_app_config = 'otree.session.apps.OtreeSessionConfig'
