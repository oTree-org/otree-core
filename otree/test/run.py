from django.test import Client
from django.utils.importlib import import_module
from threading import Thread
import sys
from Queue import Queue
import time
from otree.sessionlib.models import Session
import coverage
from otree.session import create_session, SessionTypeDirectory
import itertools
from otree.constants import special_category_bots

modules_to_include_in_coverage = ['models', 'tests', 'views']


def run_subsession(subsession):


    app_label = subsession._meta.app_label

    try:
        tests_module = import_module('{}.tests'.format(app_label))
    except ImportError:
        print '{} has no tests.py module. Exiting.'.format(app_label)
        sys.exit(0)

    failure_queue = Queue()

    # ExperimenterBot is optional
    if hasattr(tests_module, 'ExperimenterBot'):
        experimenter_bot = tests_module.ExperimenterBot(subsession)
    else:
        from otree.test.client import ExperimenterBot
        experimenter_bot = ExperimenterBot(subsession)
    experimenter_bot.start()
    t = Thread(target=experimenter_bot._play, args=(failure_queue,))
    jobs = [t]




    for player in subsession.player_set.all():
        bot = tests_module.PlayerBot(player)
        bot.start()
        t = Thread(target=bot._play, args=(failure_queue,))
        jobs.append(t)



    for job in jobs:
        job.start()

    for job in jobs:
        job.join()

    if failure_queue.qsize() == 0:
        print '{}: tests completed successfully'.format(app_label)
        return True
    else:
        print '{}: tests failed'.format(app_label)
        return False
    # assert that everyone's finished

def run_session(session_type_name):

    session = create_session(type_name=session_type_name, special_category=special_category_bots)
    session.label = '{} [bots]'.format(session.label)
    session.save()

    session_experimenter_bot = Client()
    session_experimenter_bot.get(session.session_experimenter._start_url(), follow=True)
    session_experimenter_bot.post(session.session_experimenter._start_url(), follow=True)

    # since players are assigned to groups in a background thread,
    # we need to wait for that to complete.
    while True:
        session = Session.objects.get(id=session.id)
        if session._players_assigned_to_groups:
            break
        time.sleep(1)

    for participants in session.get_participants():
        bot = Client()
        bot.get(participants._start_url(), follow=True)

    successes = []
    for subsession in session.get_subsessions():
        success = run_subsession(subsession)
        successes.append(success)
    if all(successes):
        print 'All tests in session "{}" completed successfully'.format(session_type_name)
        return True
    else:
        print 'Some tests in session "{}" failed'.format(session_type_name)
        return False

def run_session_with_coverage(session_type_name):
        app_labels = SessionTypeDirectory().get_item(session_type_name).subsession_apps

        package_names = []
        for app_label in app_labels:
            for module_name in modules_to_include_in_coverage:
                package_names.append('{}.{}'.format(app_label, module_name))
        package_names = itertools.chain(package_names)

        cov = coverage.coverage(source=package_names)
        # cov.erase() # not having desired effect
        cov.start()

        # force models.py to get loaded for coverage
        for app_label in app_labels:
            reload(sys.modules['{}.models'.format(app_label)])

        success = run_session(session_type_name)

        cov.stop()
        html_coverage_results_dir = '_coverage_results'
        percent_coverage = cov.html_report(directory=html_coverage_results_dir)
        print 'Tests {} with {}% coverage. See "{}/index.html" for detailed results.'.format(
            'succeeded' if success else 'failed',
            int(percent_coverage),
            html_coverage_results_dir
        )

        return success

def run_all_sessions_without_coverage():
    '''2014-8-17: having trouble getting coverage.py to report correct numbers
     when i test multiple sessions with coverage. so removing coverage from test_all'''
    successes = []
    for session_type in SessionTypeDirectory().select():
        session_type_name = session_type.name
        success = run_session(session_type_name)
        successes.append((session_type_name, success))

    successful_sessions = [ele[0] for ele in successes if ele[1]]
    unsuccessful_sessions = [ele[0] for ele in successes if not ele[1]]

    print '{} sessions completed successfully ({})'.format(
        len(successful_sessions),
        ', '.join(successful_sessions)
    )

    print '{} sessions completed unsuccessfully ({})'.format(
        len(unsuccessful_sessions),
        ', '.join(unsuccessful_sessions)
    )
