import os
from pathlib import Path
from subprocess import Popen
from time import sleep
import sys
from otree.main import send_termination_notice
from .base import BaseCommand

print_function = print


def get_mtimes(files) -> dict:
    mtimes = {}
    for p in files:
        try:
            mtimes[p] = p.stat().st_mtime
        except FileNotFoundError:
            pass
    return mtimes


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('port', nargs='?', default='8000')

    def handle(self, port):
        run_reloader(port)


_OTREE_CORE_DEV = os.getenv('OTREE_CORE_DEV')


def run_reloader(port):
    '''
    better to have my own autoreloader so i can easily swap between daphne/hypercorn/uvicorn
    '''

    proc = Popen(['otree', 'devserver_inner', port])

    root = Path('.')
    files_to_watch = list(root.glob('*.py')) + list(root.glob('*/*.py'))
    if _OTREE_CORE_DEV:
        # this code causes it to get stuck on proc.wait() for some reason
        # 2021-09-05: is this why it got stuck?
        files_to_watch.extend(Path('c:/otree/nodj/otree').glob('**/*.py'))
    mtimes = get_mtimes(files_to_watch)
    is_windows_venv = sys.platform.startswith("win") and sys.prefix != sys.base_prefix
    try:
        while True:
            exit_code = proc.poll()
            if exit_code is not None:
                return exit_code
            new_mtimes = get_mtimes(files_to_watch)
            changed_file = None
            for f in files_to_watch:
                if f in new_mtimes and f in mtimes and new_mtimes[f] != mtimes[f]:
                    changed_file = f
                    break
            if changed_file:
                print_function(changed_file, 'changed, restarting')
                mtimes = new_mtimes
                child_pid = send_termination_notice(port)

                # with Windows + virtualenv, proc.terminate() doesn't work.
                # sys.executable is a wrapper
                # so the actual process that is binding the port has a different pid.
                if is_windows_venv and not child_pid:
                    for retry_num in [1, 2, 3]:
                        print_function('Retrying shutdown', retry_num)
                        sleep(1)
                        child_pid = send_termination_notice(port)
                        if child_pid:
                            break
                    if not child_pid:
                        print_function('Failed to shut down')

                # child_pid is not guaranteed to be returned, so we need proc.terminate()
                proc.terminate()
                if child_pid:
                    os.kill(child_pid, 9)
                proc = Popen(['otree', 'devserver_inner', port, '--is-reload'])
            sleep(1)
    except KeyboardInterrupt:
        # handle KeyboardInterrupt (KBI) so we don't get a traceback to console.
        # The KBI is received first by the subprocess and then by the parent process.
        # Python's usual behavior is to wait until a subprocess exits before propagating the KBI
        # to the parent process.
        # but for some reason in this program, I got console output from the subprocess that seemed to come
        # after the main process exited. so, we wait.
        proc.wait(2)
