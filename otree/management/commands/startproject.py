import os
from django.core.management.commands import startproject
from django.core.management.base import CommandError
import sys

import six

import otree
from otree.management.cli import pypi_updates_cli


class Command(startproject.Command):
    help = ("Creates a new oTree project.")

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        ahelp = (
            'Tells the command to NOT prompt the user for '
            'input of any kind.')
        parser.add_argument(
            '--noinput', action='store_false', dest='interactive',
            default=True, help=ahelp)

    def handle(self, *args, **options):
        if options["interactive"]:
            answer = None
            while not answer or answer not in "yn":
                answer = six.moves.input("Include sample games? (y or n): ")
                if not answer:
                    answer = "y"
                    break
                else:
                    answer = answer[0].lower()
        else:
            answer = 'n'
        if answer == "y":
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
        self.stdout.write('Created project folder.')
