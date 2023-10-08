import logging
import os
import os.path
import os.path
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
from typing import Optional

from . import unzip
from otree.main import send_termination_notice
from .base import BaseCommand
from otree.update import check_update_needed

logger = logging.getLogger(__name__)

stdout_write = print

PORT = '8000'


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('zipfile', nargs='?')

    def handle(self, **options):
        zipfile = options.get('zipfile')
        try:
            if zipfile:
                exit_code = run_single_zipfile(zipfile)
            else:
                exit_code = autoreload_for_new_zipfiles()
            # the rest is based on django autoreload, not sure why it's done
            # this way
            if exit_code < 0:
                os.kill(os.getpid(), -exit_code)
            else:
                sys.exit(exit_code)
        except KeyboardInterrupt:
            pass


def run_single_zipfile(fn: str) -> int:
    project = Project(Path(fn))
    project.unzip_to_tempdir()
    project.start()
    # from experimenting, this responds to Ctrl+C,
    # and there is no zombie subprocess
    return project.wait()


MSG_NO_OTREEZIP_YET = 'No *.otreezip file found in this folder yet, waiting...'
MSG_FOUND_NEWER_OTREEZIP = 'Newer project found'
MSG_RUNNING_OTREEZIP_NAME = "Running {}"


def autoreload_for_new_zipfiles() -> int:
    exit_code = None
    project = get_newest_project()
    newer_project = None
    if not project:
        stdout_write(MSG_NO_OTREEZIP_YET)
        while True:
            project = get_newest_project()
            if project:
                break
            sleep(1)

    tempdirs = []
    try:
        while True:
            if newer_project:
                project = newer_project
            stdout_write(MSG_RUNNING_OTREEZIP_NAME.format(project.zipname()))
            project.unzip_to_tempdir()
            if tempdirs:
                project.take_db_from_previous(tempdirs[-1].name)

            tempdirs.append(project.tmpdir)
            project.start()
            # I used to have a try block that executed 'terminate_through_http' inside 'finally'
            # added on 2019-03-09. not sure why that was necessary
            # maybe it was just for thoroughness but now it interferes with terminating through HTTP.
            while True:
                # if process is still running, poll() returns None
                exit_code = project.poll()
                if exit_code != None:
                    return exit_code
                sleep(1)
                latest_project = get_newest_project()
                # it's possible that zipfile was deleted while the program
                # was running
                if latest_project and latest_project != project:
                    newer_project = latest_project
                    # use stdout.write because logger is not configured
                    # (django setup has not even been run)
                    stdout_write(MSG_FOUND_NEWER_OTREEZIP)
                    project.terminate()
                    break
    finally:
        # e.g. KeyboardInterrupt
        project.wait()
        for td in tempdirs:
            td.cleanup()


class Project:
    tmpdir: TemporaryDirectory = None
    _proc: subprocess.Popen

    def __init__(self, otreezip: Path):
        self._otreezip = otreezip

    def zipname(self):
        return self._otreezip.name

    def mtime(self):
        return self._otreezip.stat().st_mtime

    def __eq__(self, other):
        return self._otreezip == other._otreezip

    def unzip_to_tempdir(self):
        self.tmpdir = TemporaryDirectory()
        unzip.unzip(str(self._otreezip), self.tmpdir.name)

    def start(self):
        self.check_update_needed()
        self._proc = subprocess.Popen(
            [
                'otree',
                'devserver_inner',
                PORT,
            ],
            cwd=self.tmpdir.name,
            env=os.environ.copy(),
        )

    def delete_otreezip(self):
        self._otreezip.unlink()

    def poll(self):
        return self._proc.poll()

    def wait(self) -> int:
        return self._proc.wait()

    def terminate(self):
        child_pid = send_termination_notice(PORT)
        self._proc.terminate()
        # see the explanation in devserver about this
        os.kill(child_pid, 9)

    def take_db_from_previous(self, other_tmpdir: str):
        for item in ['db.sqlite3']:
            item_path = Path(other_tmpdir) / item
            if item_path.exists():
                shutil.move(str(item_path), self.tmpdir.name)

    def check_update_needed(self):
        """
        The main need to check if requirements.txt matches the current version
        is for oTree Studio users, since they have no way to control what version
        is installed on the server. we instead need the otreezip file to tell
        their local installation what version to use.

        We used to check if an update was needed for any otree command (devserver etc),
        but i think putting it here is more targeted with a clearer scenario.
        other cases are not really essential and there are already other ways
        to handle those.
        """
        warning = check_update_needed(
            Path(self.tmpdir.name).joinpath('requirements.txt')
        )
        if warning:
            logger.warning(warning)


MAX_OTREEZIP_FILES = 10
MSG_DELETING_OLD_OTREEZIP = 'Deleting old file: {}'

# returning the time together with object makes it easier to test
def get_newest_project() -> Optional[Project]:

    projects = [Project(path) for path in Path('.').glob('*.otreezip')]
    if not projects:
        return None

    sorted_projects = sorted(projects, key=lambda proj: proj.mtime(), reverse=True)
    newest_project = sorted_projects[0]

    # cleanup so they don't end up with hundreds of zipfiles
    for old_proj in sorted_projects[MAX_OTREEZIP_FILES:]:
        stdout_write(MSG_DELETING_OLD_OTREEZIP.format(old_proj.zipname()))
        old_proj.delete_otreezip()

    return newest_project
