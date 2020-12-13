from time import sleep
from .common import prepare_for_termination
from subprocess import Popen, TimeoutExpired
from pathlib import Path
import os

stdout_write = print


def get_mtimes(files) -> dict:
    mtimes = {}
    for p in files:
        try:
            mtimes[p] = p.stat().st_mtime
        except FileNotFoundError:
            pass
    return mtimes


def main(remaining_argv):
    '''
    better to have my own autoreloader so i can easily swap between daphne/hypercorn/uvicorn
    '''
    if not remaining_argv:
        remaining_argv = ['8000']
    port = remaining_argv[0]

    proc = Popen(['otree', 'devserver_inner'] + remaining_argv)

    root = Path('.')
    files_to_watch = [
        p
        for p in list(root.glob('*.py')) + list(root.glob('*/*.py'))
        if 'migrations' not in str(p)
    ]
    if os.getenv('OTREE_CORE_DEV'):
        # this code causes it to get stuck on proc.wait() for some reason
        files_to_watch.extend(Path('c:/otree/core/otree').glob('**/*.py'))
        files_to_watch.extend(Path('c:/otree/core/otree_startup').glob('**/*.py'))
    mtimes = get_mtimes(files_to_watch)
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
                stdout_write(changed_file, 'changed, restarting')
                mtimes = new_mtimes
                child_pid = prepare_for_termination(port)
                proc.terminate()
                if child_pid:
                    # for some reason, with Windows + virtualenv,
                    # proc is not the actual django process.
                    # so proc.terminate() will not free the port.
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
