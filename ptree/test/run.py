from django.test import Client
from django.utils.importlib import import_module
from threading import Thread
import sys
import ptree.constants
from Queue import Queue
import time
from ptree.sessionlib.models import Session
import coverage

cov = coverage.coverage()

def run_subsession(subsession):
    app_label = subsession._meta.app_label

    try:
        tests_module = import_module('{}.tests'.format(app_label))
    except ImportError:
        print '{} has no tests.py module. Exiting.'.format(app_label)
        sys.exit(0)

    failure_queue = Queue()

    experimenter_bot = tests_module.ExperimenterBot(subsession)
    experimenter_bot.start()
    t = Thread(target=experimenter_bot._play, args=(failure_queue,))
    jobs = [t]




    for participant in subsession.participant_set.all():
        bot = tests_module.ParticipantBot(participant)
        bot.start()
        t = Thread(target=bot._play, args=(failure_queue,))
        jobs.append(t)


    #cov.start()
    for job in jobs:
        job.start()

    for job in jobs:
        job.join()
    #cov.stop()
    #print cov.html_report(directory='covhtml')

    if failure_queue.qsize() > 0:
        print '{}: tests failed'.format(app_label)
    else:
        print '{}: tests completed successfully'.format(app_label)
    # assert that everyone's finished

def run(session):
    session_experimenter_bot = Client()
    session_experimenter_bot.get(session.session_experimenter._start_url(), follow=True)
    session_experimenter_bot.post(session.session_experimenter._start_url(), follow=True)

    # since participants are assigned to treatments and matches in a background thread,
    # we need to wait for that to complete.
    while True:
        session = Session.objects.get(id=session.id)
        if session.participants_assigned_to_treatments_and_matches:
            break
        time.sleep(1)

    for participant in session.participants():
        bot = Client()
        bot.get(participant._start_url(), follow=True)

    for subsession in session.subsessions():
        run_subsession(subsession)