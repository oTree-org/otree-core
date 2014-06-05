from django.test import Client
from django.utils.importlib import import_module
import os.path
import os
from threading import Thread
import sys
import ptree.constants
from Queue import Queue
from ptree.common import git_commit_timestamp
from datetime import datetime


def run_subsession(subsession, take_screenshots, screenshot_dir):
    app_label = subsession._meta.app_label

    try:
        tests_module = import_module('{}.tests'.format(app_label))
    except ImportError:
        print '{} has no tests.py module. Exiting.'.format(app_label)
        sys.exit(0)

    experimenter_bot = tests_module.ExperimenterBot(subsession, take_screenshots=take_screenshots, screenshot_dir=screenshot_dir)
    experimenter_bot.start()
    t = Thread(target=experimenter_bot.play)
    jobs = [t]


    failure_queue = Queue()

    for participant in subsession.participant_set.all():
        bot = tests_module.ParticipantBot(participant, take_screenshots=take_screenshots, screenshot_dir=screenshot_dir)
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

def run(session, take_screenshots=False):
    session_experimenter_bot = Client()
    session_experimenter_bot.get(session.session_experimenter._start_url(), follow=True)
    session_experimenter_bot.post(session.session_experimenter._start_url(), follow=True)

    if take_screenshots:
        time_stamp = datetime.now().strftime('%Y-%m-%d_%HH-%MM-%SS')
        screenshot_dir = os.path.join(os.getcwd(), 'screenshots', time_stamp)
    else:
        screenshot_dir = None

    for participant in session.participants():
        bot = Client()
        bot.get(participant._start_url(), follow=True)

    for subsession in session.subsessions():
        run_subsession(subsession, take_screenshots, screenshot_dir)