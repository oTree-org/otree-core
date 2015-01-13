#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from django.conf import settings
from django.db import transaction

from otree import constants
from otree.models.user import Experimenter
from otree.models.session import Session, SessionExperimenter, Participant
from otree.common_internal import (
    get_session_module, get_models_module, get_app_constants
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


class SessionType(object):

    def __init__(self, **kwargs):
        """this code allows default values for these attributes to be set on
        the class, that can then be overridden by SessionType instances.

        sessions.py uses this.

        """

        attrs = [
            'name',
            'app_sequence',
            'fixed_pay',
            'num_bots',
            'display_name',
            'money_per_point',
            'num_demo_participants',
            'doc',
            'vars',
            'group_by_arrival_time',
            'show_on_demo_page',
        ]

        for attr_name in attrs:
            attr_value = kwargs.get(attr_name)
            if attr_value is not None:
                setattr(self, attr_name, attr_value)
            if getattr(self, attr_name, None) is None:
                if attr_name == 'doc':
                    self.doc = ''
                if attr_name == 'vars':
                    self.vars = {}
                else:
                    msg = (
                        'Required attribute SessionType.{} is missing or None'
                    )
                    raise AttributeError(msg.format(attr_name))

        if not re.match(r'^\w+$', self.name):
            msg = (
                'Session "{}": name must be alphanumeric with no '
                'spaces (underscores allowed).'
            )
            raise ValueError(msg.format(self.name))

        if len(self.app_sequence) != len(set(self.app_sequence)):
            raise ValueError('app_sequence cannot contain duplicate elements')

        if len(self.app_sequence) == 0:
            raise ValueError('Need at least one subsession.')

        self.doc = self.doc.strip()

    def __repr__(self):
        mem = hex(id(self))
        return "<SessionType '{}' at {}>".format(self.name, mem)

    def lcm(self):
        participants_per_group_list = []
        for app_name in self.app_sequence:
            app_constants = get_app_constants(app_name)
            # if players_per_group is None, 0, etc.
            players_per_group = app_constants.players_per_group or 1
            participants_per_group_list.append(players_per_group)
        return lcmm(*participants_per_group_list)


# =============================================================================
# FUNCTIONS
# =============================================================================

def get_session_types_list(demo_only=False):
    session_types = get_session_module().session_types()
    if demo_only:
        return [
            session_type for session_type in session_types
            if session_type.show_on_demo_page
        ]
    else:
        return session_types


def get_session_types_dict(demo_only=False):
    return {
        session_type.name: session_type
        for session_type in get_session_types_list(demo_only)
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
        msg = 'Session type "{}" not found in sessions.py'
        raise ValueError(
            msg.format(session_type_name)
        )
    session = Session.objects.create(
        session_type_name=session_type.name,
        label=label, fixed_pay=session_type.fixed_pay,
        special_category=special_category,
        money_per_point=session_type.money_per_point,
        session_experimenter=SessionExperimenter.objects.create(),
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
            num_participants = session_type.num_demo_participants
        elif special_category == constants.session_special_category_bots:
            num_participants = session_type.num_bots

    # check that it divides evenly
    session_lcm = session_type.lcm()
    if num_participants % session_lcm:
        msg = (
            'SessionType {}: Number of participants ({}) does not divide '
            'evenly into group size ({})'
        ).format(session_type.name, num_participants, session_lcm)
        raise ValueError(msg)

    participants = bulk_create(
        Participant,
        [{'id_in_session': i} for i in range(1, num_participants + 1)]
    )

    subsessions = []
    for app_name in session_type.app_sequence:
        if app_name not in settings.INSTALLED_OTREE_APPS:
            msg = ("Your session contains a subsession app named '{}'. "
                   "You need to add this to INSTALLED_OTREE_APPS "
                   "in settings.py.")
            raise ValueError(msg.format(app_name))

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

    # Create experimenters and bind subsessions to them
    experimenters = bulk_create(Experimenter, [
        {'subsession': subsession}
        for subsession in subsessions
    ])
    sub_by_pk = {s.pk: s for s in subsessions}
    for experimenter in experimenters:
        idpk = experimenter.subsession_object_id
        sub_by_pk[idpk]._experimenter = experimenter
        sub_by_pk[idpk].save()

    session._create_groups_and_initialize()

    session.build_session_user_to_user_lookups()
    if session.session_type.group_by_arrival_time:
        session._set_predetermined_arrival_order()
    session.ready = True
    session.save()

    return session


default_app_config = 'otree.session.apps.OtreeSessionConfig'
