#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from django.conf import settings
from django.db import transaction

from otree import constants
from otree.models.session import Session, Participant
from otree.common_internal import (
    get_models_module, get_app_constants,
    min_players_multiple,
)


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


def get_lcm(session_type):
    min_multiple_list = []
    for app_name in session_type['app_sequence']:
        app_constants = get_app_constants(app_name)
        # if players_per_group is None, 0, etc.
        min_multiple = min_players_multiple(
            app_constants.players_per_group
        )
        min_multiple_list.append(min_multiple)
    return lcmm(*min_multiple_list)


def validate_session_type(session_type):

    required_keys = {
        'name',
        'app_sequence',
        # TODO: fixed_pay is deprecated as of 2015-05-07,
        # in favor of participation_fee. make this required at some point.
        # 'participation_fee'
        'num_bots',
        'display_name',
        'real_world_currency_per_point',
        'num_demo_participants',
        'doc',
        'group_by_arrival_time',
    }

    for key in required_keys:
        if key not in session_type:
            msg = ('Required key "{}" is missing from '
                   'session_type: {} dictionary')
            raise AttributeError(msg.format(key, session_type))

    st_name = session_type['name']
    if not re.match(r'^\w+$', st_name):
        msg = (
            'Session "{}": name must be alphanumeric with no '
            'spaces (underscores allowed).'
        )
        raise ValueError(msg.format(st_name))

    app_sequence = session_type['app_sequence']
    if len(app_sequence) != len(set(app_sequence)):
        raise ValueError(
            'app_sequence of "{}" in settings.py '
            'must not contain duplicate elements'.format(
                session_type['name']
            )
        )

    if len(app_sequence) == 0:
        raise ValueError('Need at least one subsession.')


def augment_session_type(session_type):
    new_session_type = {'doc': ''}
    new_session_type.update(settings.SESSION_TYPE_DEFAULTS)
    new_session_type.update(session_type)

    # look up new_session_type
    new_session_type['doc'] = new_session_type['doc'].strip()
    validate_session_type(new_session_type)
    return new_session_type


# =============================================================================
# FUNCTIONS
# =============================================================================

def get_session_types_list():

    return [augment_session_type(s) for s in settings.SESSION_TYPES]


def get_session_types_dict():
    return {
        session_type['name']: session_type
        for session_type in get_session_types_list()
    }


@transaction.atomic
def create_session(session_type_name, label='', num_participants=None,
                   special_category=None, _pre_create_id=None):

    # 2014-5-2: i could implement this by overriding the __init__ on the
    # Session model, but I don't really know how that works, and it seems to
    # be a bit discouraged: http://goo.gl/dEXZpv
    # 2014-9-22: preassign to groups for demo mode.

    try:
        session_type = get_session_types_dict()[session_type_name]
    except KeyError:
        msg = 'Session type "{}" not found in settings.py'
        raise ValueError(
            msg.format(session_type_name)
        )
    session = Session.objects.create(
        session_type=session_type,
        label=label,
        # FIXME: fixed_pay is deprecated on 2015-5-7, remove it eventually
        participation_fee=(
            session_type.get('participation_fee')
            or session_type.get('fixed_pay')
        ),
        special_category=special_category,
        real_world_currency_per_point=(
            session_type['real_world_currency_per_point']
        ),
        _pre_create_id=_pre_create_id,
    )

    def bulk_create(model, descriptions):
        model.objects.bulk_create([
            model(session=session, **description)
            for description in descriptions
        ])
        return model.objects.filter(session=session).order_by('pk')

    if num_participants is None:
        if special_category == constants.session_special_category_demo:
            num_participants = session_type['num_demo_participants']
        elif special_category == constants.session_special_category_bots:
            num_participants = session_type['num_bots']

    # check that it divides evenly
    session_lcm = get_lcm(session_type)
    if num_participants % session_lcm:
        msg = (
            'SessionType {}: Number of participants ({}) does not divide '
            'evenly into group size ({})'
        ).format(session_type['name'], num_participants, session_lcm)
        raise ValueError(msg)

    participants = bulk_create(
        Participant,
        [{'id_in_session': i} for i in range(1, num_participants + 1)]
    )

    subsessions = []
    for app_name in session_type['app_sequence']:

        models_module = get_models_module(app_name)
        app_constants = get_app_constants(app_name)

        round_numbers = range(1, app_constants.num_rounds + 1)

        subs = bulk_create(models_module.Subsession, [
            {'round_number': round_number}
            for round_number in round_numbers
        ])

        # Create players
        models_module.Player.objects.bulk_create([
            models_module.Player(
                session=session,
                subsession=subsession,
                round_number=round_number,
                participant=participant
            )
            for round_number, subsession in zip(round_numbers, subs)
            for participant in participants
        ])

        subsessions.extend(subs)

    session._create_groups_and_initialize()
    session.build_session_user_to_user_lookups()
    session.ready = True
    session.save()

    return session


default_app_config = 'otree.session.apps.OtreeSessionConfig'
