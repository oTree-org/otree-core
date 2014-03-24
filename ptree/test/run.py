from django.test import Client
from django.utils.importlib import import_module
import os.path
import multiprocessing
import sys
import ptree.constants

def run_subsession(subsession):
    app_label = subsession._meta.app_label
    tests_module = import_module('{}.tests'.format(app_label))

    experimenter_bot = tests_module.ExperimenterBot(subsession)
    experimenter_bot.start()
    j = multiprocessing.Process(target=experimenter_bot.play)
    jobs = [j]


    q = multiprocessing.Queue()

    for participant in subsession.participant_set.all():
        bot = tests_module.ParticipantBot(participant)
        bot.start()
        j = multiprocessing.Process(target=bot._play, args=(q,))
        jobs.append(j)

    for job in jobs:
        job.start()

    for i in range(len(jobs)):
        success = q.get() == ptree.constants.success
        if not success:
            print 'error in bot code'
            for job in jobs:
                job.terminate()
            sys.exit(-1)

    # at this point all jobs should have succeeded

    print '{}: tests completed successfully'.format(app_label)
    # assert that everyone's finished

def run(session):
    session_experimenter_bot = Client()
    session_experimenter_bot.get(session.session_experimenter.start_url(), follow=True)
    session_experimenter_bot.post(session.session_experimenter.start_url(), follow=True)

    for participant in session.participants():
        bot = Client()
        bot.get(participant.start_url(), follow=True)

    for subsession in session.subsessions():
        run_subsession(subsession)