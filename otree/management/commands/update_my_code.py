import re
import sys
from pathlib import Path
import otree
from django.core.management.base import BaseCommand
from itertools import chain


class Command(BaseCommand):
    something_changed = False

    def add_arguments(self, parser):
        ahelp = 'Tells the command to NOT prompt the user for ' 'input of any kind.'
        parser.add_argument(
            '--noinput',
            action='store_false',
            dest='interactive',
            default=True,
            help=ahelp,
        )

    def handle(self, *args, **options):

        self.stdout = sys.stdout
        self.dry_run = options["interactive"]

        if self.dry_run:
            self.scan()
            if self.something_changed:
                prompt = (
                    'You should back up your code before you proceed. '
                    'Proceed with syntax upgrade? (y or n): '
                )
                confirmed = input(prompt).lower() == 'y'
                if not confirmed:
                    sys.exit()
            else:
                self.stdout.write('Code is up to date; no changes to be made.')
                sys.exit()

        self.dry_run = False
        self.scan()

        # old format imported otree.test and otree.views, so we need to get rid of it
        _builtins = Path('.').glob('*/_builtin/__init__.py')
        for pth in _builtins:
            if 'z_autocomplete' in pth.read_text():
                new_text = (
                    Path(otree.__file__)
                    .parent.joinpath('app_template/_builtin/__init__.py')
                    .read_text()
                )
                pth.write_text(new_text)

    def scan(self):

        root = Path('.')
        html_fns = chain(
            root.glob('*/*/*.html'), root.glob('*/*.html'), root.glob('*.html')
        )
        for fn in html_fns:
            self.apply_rule_to_file(
                fn, r"% formfield (player|group)\.(\w+)", r"% formfield '\2'"
            )

    def apply_rule_to_file(self, fp: Path, before_pattern: str, after_pattern: str):
        something_changed = False
        new_lines = []
        for i, line in enumerate(fp.open(encoding='utf-8')):
            new_line = re.sub(before_pattern, after_pattern, line)
            if new_line != line:
                self.something_changed = True
                something_changed = True
                if self.dry_run:
                    self.print_change('{}, line {}\n'.format(fp, i + 1))
                    self.print_change('BEFORE: {}'.format(line))
                    self.print_change('AFTER:  {}'.format(new_line))
            new_lines.append(new_line)
        if something_changed and not self.dry_run:
            fp.write_text(''.join(new_lines))

    def print_change(self, msg):
        self.something_changed = True
        self.stdout.write(msg)
