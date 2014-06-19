from ptree import constants
from ptree.common import get_session_module
from django.conf import settings
from django.utils.importlib import import_module
from ptree.user.models import Experimenter
from ptree.sessionlib.models import Session, SessionExperimenter, SessionParticipant
from django.db import transaction


class SessionType(object):
    def __init__(self, name, subsession_apps, base_pay, num_participants, is_for_mturk=False, doc=None):
        self.name = name
        self.subsession_apps = subsession_apps
        self.base_pay = base_pay
        self.num_participants = num_participants
        self.is_for_mturk = is_for_mturk
        self.doc = doc

def get_session_types():
    return get_session_module().session_types()

def session_types_as_dict():
    return {session_type.name: session_type for session_type in get_session_types()}

def demo_enabled_session_types():
    return [session_type for session_type in get_session_types() if get_session_module().show_on_demo_page(session_type.name)]

@transaction.atomic
def create_session(type, label='', special_category=None):
    """2014-5-2: i could implement this by overriding the __init__ on the Session model, but I don't really know how that works,
    and it seems to be a bit discouraged:
    https://docs.djangoproject.com/en/1.4/ref/models/instances/#django.db.models.Model
    """
    try:
        session_type = session_types_as_dict()[type]
    except KeyError:
        raise ValueError('Session type "{}" not found in session.py'.format(type))
    session = Session(
        type=session_type.name,
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

    session_participants = []
    for i in range(session_type.num_participants):
        participant = SessionParticipant(session = session)
        participant.save()
        session_participants.append(participant)

    subsessions = []
    for app_label in session_type.subsession_apps:
        if app_label not in settings.INSTALLED_PTREE_APPS:
            raise ValueError('Your session contains a subsession app named "{}". You need to add this to INSTALLED_PTREE_APPS in settings.py.'.format(app_label))

        models_module = import_module('{}.models'.format(app_label))

        if session_type.num_participants % models_module.Match.participants_per_match:
            raise ValueError(
                'App {} requires {} participants per match, which does not divide evenly into the number of participants in this session ({}).'.format(
                    app_label,
                    models_module.Match.participants_per_match,
                    session_type.num_participants
                )
            )

        treatments = models_module.treatments()
        subsession = models_module.Subsession()
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
        for i in range(session_type.num_participants):
            participant = models_module.Participant(
                subsession = subsession,
                session = session,
                session_participant = session_participants[i]
            )
            participant.save()

        print 'Created objects for {}'.format(app_label)
        subsessions.append(subsession)


    session.chain_subsessions(subsessions)
    session.chain_participants()
    session.session_experimenter.chain_experimenters()
    session.ready = True
    session.save()
    return session

