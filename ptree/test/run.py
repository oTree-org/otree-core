from django.test import Client
from django.utils.importlib import import_module
import os.path
from threading import Thread
import sys
import ptree.constants
from Queue import Queue

def run_subsession(subsession):
    app_label = subsession._meta.app_label

    try:
        tests_module = import_module('{}.tests'.format(app_label))
    except ImportError:
        print '{} has no tests.py module. Exiting.'.format(app_label)
        sys.exit(0)

    experimenter_bot = tests_module.ExperimenterBot(subsession)
    experimenter_bot.start()
    t = Thread(target=experimenter_bot.play)
    jobs = [t]


    failure_queue = Queue()

    for participant in subsession.participant_set.all():
        bot = tests_module.ParticipantBot(participant)
        bot.start()
        t = Thread(target=bot._play, args=(failure_queue,))
        jobs.append(t)

    for job in jobs:
        job.start()

    for job in jobs:
        job.join()

    if failure_queue.qsize() > 0:
        print '{}: tests failed'.format(app_label)
    else:
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