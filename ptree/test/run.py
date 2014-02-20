import unittest
from django.test import Client
from django.utils.importlib import import_module
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os.path
import threading

def directory_name(path):
    return os.path.basename(os.path.normpath(path))

def run_subsession(subsession):
    app_label = subsession._meta.app_label
    tests_module = import_module('{}.tests'.format(app_label))

    experimenter_bot = tests_module.ExperimenterBot(subsession)
    experimenter_bot.start()
    t = threading.Thread(target=experimenter_bot.play)
    thread_list = [t]

    for participant in subsession.participants():
        bot = tests_module.ParticipantBot(participant)
        bot.start()
        t = threading.Thread(target=bot.play)
        thread_list.append(t)

    for thread in thread_list:
        thread.start()

    for thread in thread_list:
        thread.join()

    print '{}: tests completed successfully'.format(app_label)
    # assert that everyone's finished

def run(session):
    experiment_bot = Client()
    experiment_bot.get(session.session_experimenter.start_url(), follow=True)
    experiment_bot.post(session.session_experimenter.start_url(), follow=True)

    for participant in session.participants():
        bot = Client()
        bot.get(participant.start_url(), follow=True)

    for subsession in session.subsessions():
        run_subsession(subsession)