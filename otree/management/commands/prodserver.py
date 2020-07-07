import os
import logging
from django.core.management import call_command
from django.core.management.base import BaseCommand
import honcho.manager
from sys import exit as sys_exit
from django.core.management.base import BaseCommand

# made this simple class to reduce code duplication,
# and to make testing easier (I didn't know how to check that it was called
# with os.environ.copy(), especially if we patch os.environ)
class OTreeHonchoManager(honcho.manager.Manager):
    def add_otree_process(self, name, cmd):
        self.add_process(name, cmd, env=os.environ.copy(), quiet=False)


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            'addrport', nargs='?', help='Optional port number, or ipaddr:port'
        )
        parser.add_argument(
            '--no-collectstatic',
            action='store_false',
            dest='collectstatic',
            default=True,
        )

    def handle(self, *args, addrport=None, collectstatic, **options):
        if collectstatic:
            self.stdout.write('Running collectstatic ...')
            call_command('collectstatic', interactive=False, verbosity=1)
        manager = OTreeHonchoManager()
        cmd = ['otree', 'prodserver1of2']
        if addrport:
            cmd.append(addrport)
        # can't pass a list to add_process because honcho uses shell=True
        manager.add_otree_process('asgiserver', ' '.join(cmd))
        manager.add_otree_process('huey', 'otree prodserver2of2')
        manager.loop()
        sys_exit(manager.returncode)
