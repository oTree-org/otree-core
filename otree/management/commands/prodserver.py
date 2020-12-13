import logging
from django.core.management import call_command
from . import prodserver1of2

logger = logging.getLogger(__name__)


class Command(prodserver1of2.Command):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--no-collectstatic',
            action='store_false',
            dest='collectstatic',
            default=True,
        )

    def handle(self, *args, collectstatic, **options):
        if collectstatic:
            self.stdout.write('Running collectstatic ...')
            call_command('collectstatic', interactive=False, verbosity=1)
        return super().handle(*args, **options)
