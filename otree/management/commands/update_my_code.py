from django.core.management.base import BaseCommand
from glob import glob
import os.path
import sys

from contextlib import contextmanager
import io
import os

@contextmanager
def inplace_readonly(filename):
    readable = open(filename, 'r', encoding='utf-8')
    try:
        yield readable, None
    finally:
        readable.close()


@contextmanager
def inplace(filename, mode='r', buffering=-1, encoding='utf-8', errors=None,
            newline=None, backup_extension=None):
    # from Martijn Pieters blog
    """Allow for a file to be replaced with new content.

    yields a tuple of (readable, writable) file objects, where writable
    replaces readable.

    If an exception occurs, the old file is restored, removing the
    written data.

    mode should *not* use 'w', 'a' or '+'; only read-only-modes are supported.

    """

    # move existing file to backup, create new file with same permissions
    # borrowed extensively from the fileinput module
    if set(mode).intersection('wa+'):
        raise ValueError('Only read-only file modes can be used')

    backupfilename = filename + (backup_extension or os.extsep + 'bak')
    try:
        os.unlink(backupfilename)
    except os.error:
        pass
    os.rename(filename, backupfilename)
    readable = io.open(backupfilename, mode, buffering=buffering,
                       encoding=encoding, errors=errors, newline=newline)
    try:
        perm = os.fstat(readable.fileno()).st_mode
    except OSError:
        writable = open(filename, 'w' + mode.replace('r', ''),
                        buffering=buffering, encoding=encoding, errors=errors,
                        newline=newline)
    else:
        os_mode = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
        if hasattr(os, 'O_BINARY'):
            os_mode |= os.O_BINARY
        fd = os.open(filename, os_mode, perm)
        writable = io.open(fd, "w" + mode.replace('r', ''), buffering=buffering,
                           encoding=encoding, errors=errors, newline=newline)
        try:
            if hasattr(os, 'chmod'):
                os.chmod(filename, perm)
        except OSError:
            pass
    try:
        yield readable, writable
    except Exception:
        # move backup back
        try:
            os.unlink(filename)
        except os.error:
            pass
        os.rename(backupfilename, filename)
        raise
    finally:
        readable.close()
        writable.close()
        try:
            os.unlink(backupfilename)
        except os.error:
            pass

class Command(BaseCommand):
    help = "oTree: upgrade code to latest syntax."

    something_changed = False
    current_rule_number = 1

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        ahelp = (
            'Tells the command to NOT prompt the user for '
            'input of any kind.')
        parser.add_argument(
            '--noinput', action='store_false', dest='interactive',
            default=True, help=ahelp)

    def handle(self, *args, **options):

        self.stdout = sys.stdout
        self.dry_run = options["interactive"]

        if self.dry_run:
            self.scan()
            if self.something_changed:
                prompt = (
                    'The above changes will be made to your code. '
                    'You should back up your code before you proceed. '
                    'If you are using git, you should do a git commit before you proceed. '
                    'Proceed with syntax upgrade? (y or n): '
                )
                confirmed = input(prompt).lower() == 'y'
                if not confirmed:
                    sys.exit()
            else:
                self.stdout.write('Code is up to date; no changes to be made.')
                sys.exit()

        self.current_rule_number = 1
        self.dry_run = False
        self.scan()

    def scan(self):

        dry_run = self.dry_run

        python_fns = glob('*.py') + glob('*/*.py') + glob('*/*/*.py')
        for rule in PYTHON_RULES:
            self.print_rule_header()
            # don't use recursive, in case there is a venv.
            for fn in python_fns:
                self.apply_rule_to_file(fn, rule)

        html_fns = glob('**/*.html', recursive=True)
        for rule in HTML_RULES:
            self.print_rule_header()
            for fn in html_fns:
                self.apply_rule_to_file(fn, rule)

        test_fns = glob('tests.py') + glob('*/tests.py') + glob('*/*/tests.py')
        for rule in TESTS_RULES:
            self.print_rule_header()
            for fn in test_fns:
                self.apply_rule_to_file(fn, rule)

        if os.path.isfile('Procfile'):
            for rule in PROCFILE_RULES:
                self.print_rule_header()
                self.apply_rule_to_file('Procfile', rule)

        self.print_rule_header()
        view_fns = glob('views.py') + glob('*/views.py') + glob('*/*/views.py')
        for fn in view_fns:
            new_fn = fn.replace('views.py', 'pages.py')
            if dry_run:
                self.print_change('Rename {} to {}\n'.format(fn, new_fn))
            else:
                os.rename(fn, new_fn)

        self.print_rule_header()
        for fn in ['requirements_base.txt', 'requirements.txt', 'requirements_heroku.txt']:
            if os.path.isfile(fn):
                if dry_run:
                    with open(fn, 'r') as infh:
                        for line in infh:
                            if line.startswith('Django=='):
                                self.print_change(fn + '\n')
                                self.print_change('REMOVE: {}'.format(line))
                else:
                    with inplace(fn, 'r') as (infh, outfh):
                        for line in infh:
                            if line.startswith('otree-core'):
                                outfh.write('otree\n')
                            else:
                                l_django = line.startswith('Django==')
                                # remove obsolete comments about including Django
                                l_explicitly = 'explicitly' in line
                                l_collectstatic = 'collectstatic' in line
                                if not (l_django or l_collectstatic or l_explicitly):
                                    outfh.write(line)

        self.print_rule_header()
        if os.path.isfile('.gitignore'):
            temp_wildcard = '__temp*'
            with open('.gitignore', 'r') as file:
                temp_wildcard_found = temp_wildcard in file.read()
            if not temp_wildcard_found:
                if dry_run:
                    self.print_change('ADD "__temp*" to .gitignore\n')
                else:
                    with open('.gitignore', 'a') as file:
                        file.write('\n' + temp_wildcard)

        self.print_rule_header()
        for fn in ['_templates/global/Base.html', '_templates/global/Page.html']:
            rule = Rule(
                '{% extends "otree/FormPage.html" %}',
                '{% extends "otree/Page.html" %}',
            )
            if os.path.isfile(fn):
                self.apply_rule_to_file(fn, rule)

    def apply_rule_to_file(self, fn, rule):
        if self.dry_run:
            cm = inplace_readonly(fn)
        else:
            cm = inplace(fn, 'r')
        with cm as (infh, outfh):
            lines = list(infh)
            for i, line in enumerate(lines):
                new_line = rule.new_line(line)
                if new_line != line:
                    if self.dry_run:
                        self.print_change('{}, line {}\n'.format(fn, i + 1))
                        self.print_change('BEFORE: {}'.format(line))
                        self.print_change('AFTER:  {}'.format(new_line))
                if not self.dry_run:
                    outfh.write(new_line)

    def print_rule_header(self):
        self.stdout.write('****APPLYING RULE #{}\n'.format(self.current_rule_number))
        self.current_rule_number += 1

    def print_change(self, msg):
        self.something_changed = True
        self.stdout.write(msg)

    # TODO: remove migrations?

class Rule:
    def __init__(self, old_token, new_token, description=None):
        self.old_token = old_token
        self.new_token = new_token
        self.description = description or 'rename {} to {}'.format(old_token, new_token)

    def new_line(self, line):
        return line.replace(self.old_token, self.new_token)


PYTHON_RULES = [
    Rule(
        'form_model = models.Player',
        "form_model = 'player'",
        "change <form_model = models.Player> to <form_model = 'player'>"
    ),
    # if they're using Django models, this won't work.
    Rule(
        '= models.CharField',
        '= models.StringField',
    ), # what about initial=None and default=None? maybe do a simple lookahead
    # if they're using Django models, this won't work.
    Rule(
        '= models.TextField',
        '= models.LongStringField',
    ), # what about initial=None and default=None?
    Rule(
        'form_model = models.Group',
        "form_model = 'group'",
        "change <form_model = models.Player> to <form_model = 'group'>"
    ),
    Rule(
        'before_session_starts',
        'creating_session',
    ),
    # if they are using Django models, or if there are migrations, this won't work.
    # Rule(
    #     'verbose_name',
    #    'label',
    # ),
    Rule(
        'SliderInput',
        'Slider',
    )
]

TESTS_RULES = [
    Rule(
        'views',
        'pages',
        'fix references to views.py'
    ),
]

HTML_RULES = [
    Rule(
        '{% load otreechat %}',
        ''
    ),
    Rule(
        'with label=',
        'label=',
        'remove unnecessary "with" in formfield tag'
    ),
    Rule(
        'otree_tags',
        'otree',
    ),
    # someone might have created their own next button;
    # we don't want to break the selector for that.
    #Rule(
    #    '.next-button',
    #    '.otree-btn-next'
    #),
    Rule(
        '.otree-next-button',
        '.otree-btn-next'
    ),
    Rule(
        '#otree-body',
        '.otree-body'
    ),
    Rule(
        '#otree-title',
        '.otree-title'
    ),
    Rule(
        '#otree-timeout',
        '.otree-timer'
    ),
    Rule(
        '#otree-form-errors',
        '.otree-form-errors'
    ),
    # rarely used rules...will just slow things down
    #Rule(
    #    '#otree-wait-page-body',
    #    '.otree-wait-page'
    #),
    #Rule(
    #    '#otree-wait-page-title-text',
    #    '.otree-wait-page__title'
    #),
    #Rule(
    #    '#otree-wait-page-body-text',
    #    '.otree-wait-page__body'
    #),
]


PROCFILE_RULES = [
    Rule(
        'web: otree webandworkers',
        'web: otree runprodserver1of2',
    ),
    Rule(
        'timeoutworker: otree timeoutworker',
        'worker: otree runprodserver2of2',
    )
]

