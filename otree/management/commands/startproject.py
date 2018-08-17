import os
from django.core.management.commands import startproject
from django.core.management.base import CommandError
import sys
import otree
from otree_startup import pypi_updates_cli


class Command(startproject.Command):
    help = ("Creates a new oTree project.")

    def add_arguments(self, parser):
        '''need this so we can test startproject automatically'''
        super().add_arguments(parser)
        parser.add_argument(
            '--noinput', action='store_false', dest='interactive',
            default=True)

    def handle(self, *args, **options):
        if os.path.isfile('settings.py') and os.path.isfile('manage.py'):
            self.stdout.write(
                'You are trying to create a project but it seems you are '
                'already in a project folder (found settings.py and manage.py).'
            )
            sys.exit(-1)

        if options['interactive']:
            answer = input("Include sample games? (y or n): ")
        else:
            answer = 'n'
        if answer and answer[0].lower() == "y":
            project_template_path = (
                "https://github.com/oTree-org/oTree/archive/master.zip")
        else:
            project_template_path = os.path.join(
                os.path.dirname(otree.__file__), 'project_template')

        if options.get('template', None) is None:
            options['template'] = project_template_path
        try:
            super().handle(*args, **options)
        except CommandError as exc:
            is_macos = sys.platform.startswith('darwin')
            if is_macos and 'CERTIFICATE_VERIFY_FAILED' in str(exc):
                py_major, py_minor = sys.version_info[:2]
                msg = (
                    'CERTIFICATE_VERIFY_FAILED: '
                    'Before downloading the sample games, '
                    'you need to install SSL certificates. '
                    'Usually this can be resolved by entering this command:\n'
                    '/Applications/Python\\ {}.{}/Install\\ Certificates.command'
                ).format(py_major, py_minor)
                self.stdout.write(msg)
                sys.exit(-1)
            raise
        try:
            pypi_updates_cli()
        except:
            pass
        # this assumes the 'directory' arg was unused, which will be true
        # for 99% of oTree users.
        msg = (
            'Created project folder.\n'
            'Enter "cd {}" to move inside the project folder, '
            'then start the server with "otree devserver".' #
        ).format(options['name'])
        self.stdout.write(msg)
