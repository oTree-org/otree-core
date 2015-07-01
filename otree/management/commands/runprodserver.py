import os
from optparse import make_option

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
import honcho.command
import honcho.manager


class HonchoConifg(object):
    """Shim for arguments passed into honcho's ``command_start``."""

    # Defaults for honcho
    app_root = os.path.abspath('.')
    concurrency = None
    env = '.env'
    processes = ()
    quiet = None

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class Command(BaseCommand):
    help = 'Run otree services for the production environment.'

    option_list = BaseCommand.option_list + (
        make_option(
            '--procfile',
            action='store',
            dest='procfile',
            default='./Procfile',
            help=(
                'The path to the Procfile that should be executed. '
                'The default is ./Procfile')),
        make_option(
            '--no-collectstatic',
            action='store_false',
            dest='collectstatic',
            default=True,
            help=(
                'By default we will collect all static files into the '
                'directory configured in your settings. Disable it with this '
                'switch if you want to do it manually.')),
        make_option(
            '--port',
            action='store',
            type=int,
            dest='port',
            default=None,
            help=(
                'The port that the wsgi server should run on. '
                'It defaults to 5000. This value can be set by the '
                'environment variable $PORT.')),
    )

    default_port = 5000

    def get_port(self, suggested_port):
        if suggested_port is None:
            suggested_port = os.environ.get('PORT', None)
        try:
            return int(suggested_port)
        except (ValueError, TypeError):
            return self.default_port

    def configure_production_mode(self):
        os.environ.setdefault('OTREE_PRODUCTION', '1')

    def handle(self, *args, **options):
        self.configure_production_mode()

        port = self.get_port(options['port'])
        procfile = options['procfile']
        collectstatic = options['collectstatic']

        args = HonchoConifg(
            procfile=procfile,
            port=port,
        )

        if collectstatic:
            self.stdout.write('Running collectstatic ...', ending='')
            call_command('collectstatic', interactive=False, verbosity=1)

        try:
            honcho.command.command_start(args)
        except honcho.command.CommandError as error:
            raise CommandError(error)
