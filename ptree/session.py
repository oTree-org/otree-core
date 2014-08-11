from ptree import constants
from ptree.common import get_session_module
from django.conf import settings
from django.utils.importlib import import_module
from ptree.user.models import Experimenter
from ptree.sessionlib.models import Session, SessionExperimenter, SessionParticipanRENAMEt
from django.db import transaction
from collections import defaultdict

class SessionType(object):
    def __init__(self, name, subsession_apps, base_pay, session_participanRENAMEts_per_session,
                 session_participanRENAMEts_per_demo_session = None, is_for_mturk=False, doc=None, assign_to_matches_on_the_fly=False):
        self.name = name
        self.subsession_apps = subsession_apps
        self.base_pay = base_pay
        self.session_participanRENAMEts_per_session = session_participanRENAMEts_per_session
        self.session_participanRENAMEts_per_demo_session = session_participanRENAMEts_per_demo_session
        self.is_for_mturk = is_for_mturk
        self.doc = doc.strip()

        # on MTurk, assign_to_matches_on_the_fly = True
        self.assign_to_matches_on_the_fly = assign_to_matches_on_the_fly

def get_session_types():
    return get_session_module().session_types()

def session_types_as_dict():
    return {session_type.name: session_type for session_type in get_session_types()}

def demo_enabled_session_types():
    return [session_type for session_type in get_session_types() if get_session_module().show_on_demo_page(session_type.name)]

@transaction.atomic
def create_session(type_name, label='', special_category=None):
    """2014-5-2: i could implement this by overriding the __init__ on the Session model, but I don't really know how that works,
    and it seems to be a bit discouraged:
    https://docs.djangoproject.com/en/1.4/ref/models/instances/#django.db.models.Model
    """
    try:
        session_type = session_types_as_dict()[type_name]
    except KeyError:
        raise ValueError('Session type "{}" not found in session.py'.format(type_name))
    session = Session(
        type_name=session_type.name,
        label=label,
        is_for_mturk=session_type.is_for_mturk,
        base_pay=session_type.base_pay,
        special_category=special_category,
    )

    session.save()

    if len(session_type.subsession_apps) == 0:
        raise ValueError('Need at least one subsession.')

    # check that it divides evenly

    session_experimenter = SessionExperimenter()
    session_experimenter.save()
    session.session_experimenter = session_experimenter

    session_participanRENAMEts = []

    if special_category == constants.special_category_demo:
        session_participanRENAMEts_per_session = session_type.session_participanRENAMEts_per_demo_session
    else:
        session_participanRENAMEts_per_session = session_type.session_participanRENAMEts_per_session

    for i in range(session_participanRENAMEts_per_session):
        session_participanRENAMEt = SessionParticipanRENAMEt(session = session)
        session_participanRENAMEt.save()
        session_participanRENAMEts.append(session_participanRENAMEt)

    subsessions = []
    round_counts = defaultdict(int)
    for app_label in session_type.subsession_apps:
        if app_label not in settings.INSTALLED_PTREE_APPS:
            raise ValueError('Your session contains a subsession app named "{}". You need to add this to INSTALLED_PTREE_APPS in settings.py.'.format(app_label))

        round_counts[app_label] += 1
        models_module = import_module('{}.models'.format(app_label))

        if session_participanRENAMEts_per_session % models_module.Match.players_per_match:
            raise ValueError(
                'App {} requires {} players per match, which does not divide evenly into the number of players in this session ({}).'.format(
                    app_label,
                    models_module.Match.players_per_match,
                    session_participanRENAMEts_per_session
                )
            )

        #FIXME: make sure this returns the same thing each time, so that you can reassign to the same treatment
        treatments = models_module.treatments()
        for t_index, t in enumerate(treatments):
            t._index_within_subsession = t_index

        subsession = models_module.Subsession(round_number = round_counts[app_label])
        subsession.save()
        for t in treatments:
            t.subsession = subsession
            t.save()



        session.add_subsession(subsession)
        experimenter = Experimenter(session=session)
        experimenter.subsession = subsession
        experimenter.save()

        subsession._experimenter = experimenter
        subsession.save()
        for i in range(session_participanRENAMEts_per_session):
            session_participanRENAMEt = models_module.Player(
                subsession = subsession,
                session = session,
                session_participanRENAMEt = session_participanRENAMEts[i]
            )
            session_participanRENAMEt.save()

        if session.type().assign_to_matches_on_the_fly:
            # create matches at the beginning because we will not need to delete players
            # unlike the lab setting, where there may be no-shows
            subsession._create_empty_matches()

        print 'Created objects for {}'.format(app_label)
        subsessions.append(subsession)


    session.chain_subsessions(subsessions)
    session.chain_players()
    session.session_experimenter.chain_experimenters()
    session.ready = True
    session.save()
    return session

