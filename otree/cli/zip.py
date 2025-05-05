'''
Even though this command doesn't require Django to be setup,
it should run after django.setup() just to make sure it doesn't
crash when pushed to Heroku
'''

from .base import BaseCommand
import tarfile
import os
import logging
from pathlib import Path
import sys
import re
from otree import __version__ as otree_version

logger = logging.getLogger(__name__)

# need to resolve to expand path
PROJECT_PATH = Path('.').resolve()

# don't want to use the .gitignore format, it looks like a mini-language
# https://git-scm.com/docs/gitignore#_pattern_format

# TODO: maybe some of these extensions like .env, staticfiles could legitimately exist in subfolders.
EXCLUDED_PATH_ENDINGS = '~ .git db.sqlite3 .pyo .pyc .pyd .idea .DS_Store .otreezip venv _static_root staticfiles __pycache__ .env'.split()

OVERWRITE_TOKEN = 'oTree-may-overwrite-this-file'
DONT_OVERWRITE_TOKEN = 'oTree-may-not-overwrite-this-file'


def filter_func(tar_info: tarfile.TarInfo):
    path = tar_info.path

    for ending in EXCLUDED_PATH_ENDINGS:
        if path.endswith(ending):
            return None

    if '__temp' in path:
        return None

    # size is in bytes
    kb = tar_info.size >> 10
    if kb > 500:
        logger.info(f'Adding large file ({kb} KB): {path}')

    # make sure all dirs are writable, so their children can be deleted,
    # so that otree unzip/zipserver work as expected.
    # we were getting some folders with permission 16749.
    tar_info.mode |= 0o222
    return tar_info


class Command(BaseCommand):
    help = "Zip into an archive"

    def handle(self, **options):
        zip_project(PROJECT_PATH)

    def run_from_argv(self, argv):
        '''
        copy-pasted from 'unzip' command
        '''

        parser = self.create_parser(argv[0], argv[1])
        options = parser.parse_args(argv[2:])
        cmd_options = vars(options)
        self.handle(**cmd_options)


def zip_project(project_path: Path):
    # always use the same name for simplicity and so that we don't get bloat
    # or even worse, all the previous zips being included in this one
    # call it zipped.tar so that it shows up alphabetically last
    # (using __temp prefix makes it show up in the middle, because it's a file)
    archive_name = f'{project_path.name}.otreezip'

    settings_file = project_path / 'settings.py'
    if not settings_file.exists():
        msg = (
            "Cannot find oTree settings. "
            "You must run this command from the folder that contains your "
            "settings.py file."
        )
        logger.error(msg)
        sys.exit(1)

    for fn, new_text in fix_reqs_files(project_path).items():
        project_path.joinpath(fn).write_text(new_text)

    try:
        validate_reqs_files(project_path)
    except RequirementsError as exc:
        logger.error(str(exc))
        sys.exit(1)

    # once Heroku upgrades their default python version, we can remove this runtime stuff.
    # we should just overwrite the existing runtime. because maybe it has something old.
    # (e.g. if it was downloaded from otree hub)
    runtime_txt = project_path / '.python-version'
    runtime_txt.write_text('3.12.5')
    with tarfile.open(archive_name, 'w:gz') as tar:
        # if i omit arcname, it nests the project 2 levels deep.
        # if i say arcname=proj, it puts the whole project in a folder.
        # if i say arcname='', it has 0 levels of nesting.
        tar.add(project_path, arcname='', filter=filter_func)
    runtime_txt.unlink()
    logger.info(f'Saved your code into file "{archive_name}"')


def fix_reqs_files(project_path: Path) -> dict:
    rpath = project_path.joinpath('requirements.txt')
    rbpath = project_path.joinpath('requirements_base.txt')
    original_rtxt = rpath.read_text('utf8')
    original_rbtxt = rbpath.read_text('utf8') if rbpath.exists() else ''

    can_overwrite = False
    if OVERWRITE_TOKEN in original_rtxt:
        can_overwrite = True
    elif DONT_OVERWRITE_TOKEN not in original_rtxt:
        ans = input(
            "Do you want oTree to automatically keep your requirements files up to date?\n"
            "(Enter 'n' if you have custom requirements in requirements.txt or requirements_base.txt)\n"
            "(y/n): "
        ).lower()
        if ans == 'y':
            can_overwrite = True
        elif ans == 'n':
            return {rpath.name: f'# {DONT_OVERWRITE_TOKEN}\n' + original_rtxt}
        else:
            sys.stdout.write('Answer not recognized; skipping\n')
            can_overwrite = False

    if can_overwrite:
        d = {rpath.name: REQS_DEFAULT}
        if rbpath.exists():
            d[rbpath.name] = REQS_BASE_DEFAULT
        return d
    else:
        return {}


def get_non_comment_lines(f):
    lines = []
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            lines.append(line)
    return lines


class RequirementsError(Exception):
    pass


REQS_BASE_DEFAULT = '''\
# You should put your requirements in requirements.txt instead.
# You can delete this file.
'''

# we do otree== because it ensures that the version on Heroku
# always matches what's installed locally.
# the previous argument for using >= was that if you download a new zipfile and run devserver,
# otree will complain that you are using the wrong version.
# but the upgrade check only looks for lines starting with otree>=.
_REQS_DEFAULT_FMT = f'''\
# {OVERWRITE_TOKEN}
# IF YOU MODIFY THIS FILE, remove these comments.
# otherwise, oTree will automatically overwrite it.
otree%s=={otree_version}
psycopg2>=2.8.4
sentry-sdk>=0.7.9
'''

REQS_DEFAULT = _REQS_DEFAULT_FMT % ''


def validate_reqs_files(project_path: Path):
    rpath = project_path / 'requirements.txt'
    rbpath = project_path / 'requirements_base.txt'

    with rpath.open(encoding='utf8') as f:
        rlines = get_non_comment_lines(f)

    if rbpath.exists():
        with rbpath.open(encoding='utf8') as f:
            rblines = get_non_comment_lines(f)

        # check duplicates
        already_seen = set()
        for ln in rlines + rblines:
            m = re.match(r'(^[\w-]+).*?', ln)
            if m:
                package = m.group(1)
                if package in already_seen:
                    msg = (
                        f'"{package}" is listed more than once '
                        'in your requirements_base.txt & requirements.txt. '
                    )
                    raise RequirementsError(msg)
                already_seen.add(package)
    else:
        REFERENCE_TO_REQS_BASE = '-r requirements_base.txt'
        if REFERENCE_TO_REQS_BASE in rlines:
            msg = f'your requirements.txt has a line that says "{REFERENCE_TO_REQS_BASE}". You should remove that line.'
            raise RequirementsError(msg)

    # better to tell people about this so they stop deleting that line.
    # also simpler to implement and test the warning
    if not 'psycopg2' in rpath.read_text('utf8'):
        msg = 'You should add a line to your requirements.txt that says: psycopg2'
        raise RequirementsError(msg)
