import contextlib
import os
import sys
from StringIO import StringIO


@contextlib.contextmanager
def add_path(path):
    """
    ::

        with add_path(new_sys_path):
            import strange_module
    """
    sys.path.insert(0, path)
    yield
    sys.path.pop(sys.path.index(path))


@contextlib.contextmanager
def capture_stdout(target=None):
    original = sys.stdout
    if target is None:
        target = StringIO()
    sys.stdout = target
    yield target
    target.seek(0)
    sys.stdout = original


@contextlib.contextmanager
def cd(directory):
    """
    ::

        with cd(new_cwd):
            os.walk('.')
    """
    old_path = os.getcwd()
    os.chdir(directory)
    yield
    os.chdir(old_path)
