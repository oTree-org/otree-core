from django.utils.importlib import import_module
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from otree.session.models import create_session
import os.path
import otree.test.run
import os
from django.core.management import call_command
from threading import Thread


class Command(BaseCommand):
    help = "oTree: Run the test bots for a session and take screenshots"
    args = '[session_name]'

    def handle(self, *args, **options):
        print 'Creating session...'
        if len(args) > 1:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        if len(args) == 1:
            name = args[0]
        else:
            name = None

        # need to run the web server so that we can generate screenshots
        # not sure if this will terminate properly when the tests finish running. also, will the server run in time
        # to take the screenshot?
        t = Thread(target=call_command, args=('runserver',))
        t.start()

        session = create_session(name)
        session.label = '{} [test]'.format(session.label)
        session.save()

        otree.test.run.run(session, take_screenshots=True)






