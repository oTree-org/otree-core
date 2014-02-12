import sys

from django.conf import settings
from django.utils.importlib import import_module

from ptree.sessionlib.models import Session, SessionExperimenter, SessionParticipant
from ptree.user.models import Experimenter

def create(label, is_for_mturk, sequence, base_pay, num_participants):
    session = Session(label=label,
                                is_for_mturk=is_for_mturk,
                                base_pay=base_pay)

    session.save()


    try:
        session_experimenter = SessionExperimenter()
        session_experimenter.save()
        session.session_experimenter = session_experimenter

        session_participants = []
        for i in range(num_participants):
            participant = SessionParticipant(session = session)
            participant.save()
            session_participants.append(participant)

        experiments = []
        for app_name in sequence:
            if app_name not in settings.INSTALLED_PTREE_APPS:
                print 'Before running this command you need to add "{}" to INSTALLED_PTREE_APPS.'.format(app_name)
                return

            models_module = import_module('{}.models'.format(app_name))
            experiment = models_module.create_experiment_and_treatments()
            experiment.save()
            [t.save() for t in experiment.treatments()]

            session.add_experiment(experiment)
            experimenter = Experimenter(session=session)
            experimenter.experiment = experiment
            experiment.experimenter = experimenter
            experimenter.save()
            for i in range(num_participants):
                participant = models_module.Participant(experiment = experiment,
                                                        session = session,
                                                        session_participant = session_participants[i])
                participant.save()

            # check that bonus calculation doesn't throw an error, to prevent downstream problems.
            # just check the first participant, to save time.
            for participant in list(experiment.participants())[:1]:
                exception = False
                wrong_type = False
                bonus = None
                try:
                    bonus = participant.bonus()
                except:
                    exception = True
                else:
                    if (not isinstance(bonus, int)) and bonus != None:
                        wrong_type = True
                if exception or wrong_type:
                    print '{}: participant.bonus() must either return an integer, or None if it cannot be calculated yet.'.format(app_name)
                    if wrong_type:
                        print 'Currently, the return value is {}'.format(bonus)
                    elif exception:
                        print 'Currently, it raises an exception.'
                    sys.exit(1)


            print 'Created objects for {}'.format(app_name)
            experiments.append(experiment)


        session.chain_experiments(experiments)
        session.chain_participants()
        session.session_experimenter.chain_experimenters()
    except:
        session.delete()
        raise