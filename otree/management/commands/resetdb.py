from optparse import make_option
import os
import sys

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import NoArgsCommand
from django.utils import six


class Command(NoArgsCommand):
    help = (
        "Resets your development database to a fresh state. "
        "All data will be deleted.")

    option_list = NoArgsCommand.option_list + (
        make_option('--noinput', action='store_false', dest='interactive',
                    default=True, help=(
                        'Tells the resetdb command to NOT prompt the user for '
                        'input of any kind.')),
    )

    def handle_noargs(self, **options):
        self.interactive = options.get('interactive')

        default_db = settings.DATABASES['default']
        if 'sqlite' not in default_db['ENGINE']:
            sys.stderr.write(
                "ERROR: cannot set back a database that is using the "
                "{backend} backend. We only support sqlite databases so far."
                .format(backend=default_db['ENGINE']))
            sys.exit(1)

        db_file_name = default_db['NAME']
        # Delete DB file if it already exists.
        if os.path.exists(db_file_name):
            if self.interactive:
                answer = None
                self.stdout.write(
                    "Resetting the DB will destroy all current data. "
                    "The DB file {0} will be deleted.\n".format(db_file_name))
                while not answer or answer not in "yn":
                    answer = six.moves.input("Do you wish to proceed? [yN] ")
                    if not answer:
                        answer = "n"
                        break
                    else:
                        answer = answer[0].lower()
                if answer != "y":
                    return

            self.stdout.write("Deleting {0} ...\n".format(db_file_name))
            os.unlink(db_file_name)

        call_command('migrate', interactive=self.interactive)
