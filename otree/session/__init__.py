from otree import constants
from otree.common_internal import get_session_module, get_models_module, get_app_constants
from django.conf import settings
from otree.models.user import Experimenter
from otree.session.models import Session, SessionExperimenter, Participant
from django.db import transaction
from collections import defaultdict
from itertools import groupby
import re



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
        """this code allows default values for these attributes to be set on the class,
         that can then be overridden by SessionType instances.
         sessions.py uses this.
         """

        attrs = [
            'name',
            'subsession_apps',
            'fixed_pay',
            'num_bots',
            'display_name',
            'money_per_point',
            'num_demo_participants',
            'doc',

            # on MTurk, assign_to_groups_on_the_fly = True
            'assign_to_groups_on_the_fly',
            'show_on_demo_page',
        ]

        for attr_name in attrs:
            attr_value = kwargs.get(attr_name)
            if attr_value is not None:
                setattr(self, attr_name, attr_value)
            if attr_name != 'doc':
                assert getattr(self, attr_name) is not None

        if not re.match(r'^\w+$', self.name):
            raise ValueError('Session "{}": name must be alphanumeric with no spaces (underscores allowed).'.format(self.name))

        if len(self.subsession_apps) == 0:
            raise ValueError('Need at least one subsession.')

        self.doc = self.doc.strip()



    def lcm(self):
        participants_per_group_list = []
        for app_name in self.subsession_apps:
            app_constants = get_app_constants(app_name)
            # if players_per_group is None, 0, etc.
            players_per_group = app_constants.players_per_group or 1
            participants_per_group_list.append(players_per_group)
        return lcmm(*participants_per_group_list)

def session_types_list(demo_only=False):
    session_types = get_session_module().session_types()
    if demo_only:
        return [
            session_type for session_type in session_types
            if session_type.show_on_demo_page
        ]
    else:
        return session_types


def session_types_dict(demo_only=False):
    return {
        session_type.name: session_type
        for session_type in session_types_list(demo_only)
    }


@transaction.atomic
def create_session(type_name, label='', num_participants=None,
                  special_category=None, preassign_players_to_groups=False):

    #~ 2014-5-2: i could implement this by overriding the __init__ on the
    #~ Session model, but I don't really know how that works, and it seems to
    #~ be a bit discouraged:
    #~ https://docs.djangoproject.com/en/1.4/ref/models/instances/#django.db.models.Model
    #~ 2014-9-22: preassign to groups for demo mode.

    try:
        session_type = session_types_dict()[type_name]
    except KeyError:
        raise ValueError('Session type "{}" not found in sessions.py'.format(type_name))
    session = Session(
        type_name=session_type.name,
        label=label,
        fixed_pay=session_type.fixed_pay,
        special_category=special_category,
        money_per_point = session_type.money_per_point,
    )

    session.save()

    session_experimenter = SessionExperimenter()
    session_experimenter.save()
    session.session_experimenter = session_experimenter

    participants = []

    if num_participants is None:
        if special_category == constants.session_special_category_demo:
            num_participants = session_type.num_demo_participants
        elif special_category == constants.session_special_category_bots:
            num_participants = session_type.num_bots

    # check that it divides evenly
    session_lcm = session_type.lcm()
    if num_participants % session_lcm:
        raise ValueError(
            'SessionType {}: Number of participants ({}) does not divide evenly into group size ({})'.format(
                session_type.name,
                num_participants,
                session_lcm
            )
        )


    for i in range(num_participants):
        participant = Participant(session = session)
        participant.save()
        participants.append(participant)

    subsessions = []
    for app_name in session_type.subsession_apps:
        if app_name not in settings.INSTALLED_OTREE_APPS:
            msg = ("Your session contains a subsession app named '{}'. "
                   "You need to add this to INSTALLED_OTREE_APPS "
                   "in settings.py.")
            raise ValueError(msg.format(app_name))

        models_module = get_models_module(app_name)
        app_constants = get_app_constants(app_name)

        round_numbers = range(1, app_constants.number_of_rounds+1)
        for round_number in round_numbers:
            subsession = models_module.Subsession(
                round_number = round_number,
                )
            subsession.save()

            session.add_subsession(subsession)

            experimenter = Experimenter(session=session)
            experimenter.subsession = subsession
            experimenter.save()
            subsession._experimenter = experimenter

            subsession.save()

            for i in range(num_participants):
                player = models_module.Player(
                    subsession = subsession,
                    session = session,
                    participant = participants[i]
                )
                player.save()

            if session.type().assign_to_groups_on_the_fly:
                # create groups at the beginning because we will not need to
                # delete players unlike the lab setting, where there may be
                # no-shows
                subsession._create_empty_groups()

            subsessions.append(subsession)

    session.chain_subsessions(subsessions)
    session.chain_players()
    session.session_experimenter.chain_experimenters()
    if preassign_players_to_groups:
        session._assign_groups_and_initialize()
    session.build_session_user_to_user_lookups()
    session.ready = True
    session.save()
    return session


default_app_config = 'otree.session.apps.OtreeSessionConfig'
