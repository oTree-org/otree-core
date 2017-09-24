import os
import sys
import logging

import honcho.manager

from channels.log import setup_logger

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


# made this simple class to reduce code duplication,
# and to make testing easier (I didn't know how to check that it was called
# with os.environ.copy(), especially if we patch os.environ)
class OTreeHonchoManager(honcho.manager.Manager):
    def add_otree_process(self, name, cmd):
        self.add_process(name, cmd, env=os.environ.copy(), quiet=False)


class Command(BaseCommand):

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.logger = setup_logger('django.channels', self.verbosity)
        self.honcho = OTreeHonchoManager()
        self.setup_honcho(options)
        self.honcho.loop()
        sys.exit(self.honcho.returncode)

    def setup_honcho(self, options):

        daphne_cmd = 'daphne otree.asgi:channel_layer -b 0.0.0.0 -p 8000'

        honcho = self.honcho

        #cov_prefix = 'coverage run {}'

        botworker_cmd = 'coverage run manage.py botworker'
        #runworker_cmd = cov_prefix.format('manage.py runworker')
        runworker_cmd = 'python manage.py runworker'

        commands = [daphne_cmd] + 2 * [runworker_cmd]
        #commands = [daphne_cmd, botworker_cmd]

        for i, command in enumerate(commands):
            honcho.add_otree_process('worker{}'.format(i), command)
