import shutil
from importlib import import_module
from pathlib import Path
from sys import exit as sys_exit

import otree
from .base import BaseCommand
from otree.common import app_name_validity_message

print_function = print


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('name')

    def handle(self, name):
        dest = Path(name)
        if dest.exists():
            sys_exit(
                f'There is already an app called "{name}" '
                'in this folder. Either delete that folder first, or use a different name.'
            )
        try:
            import_module(name)
        except ModuleNotFoundError:
            pass
        else:
            sys_exit(
                f"'{name}' conflicts with the name of an existing Python "
                "module. Please try "
                "another name."
            )
        msg = app_name_validity_message(name)
        if msg:
            sys_exit(msg)

        use_noself = False
        for p in Path('.').glob('*/__init__.py'):
            if 'class Player' in p.read_text('utf8'):
                use_noself = True
        # if it's an empty project, we should default to noself.
        if not list(Path('.').glob('*/models.py')):
            use_noself = True
        if use_noself:
            src = Path(otree.__file__).parent / 'app_template_lite'
            shutil.copytree(src, dest)
            models_path = dest.joinpath('__init__.py')
        else:
            src = Path(otree.__file__).parent / 'app_template'
            shutil.copytree(src, dest)
            dest.joinpath('templates/app_name').rename(
                dest.joinpath('templates/', name)
            )
            models_path = dest.joinpath('models.py')
        models_path.write_text(models_path.read_text().replace("{{ app_name }}", name))
        print_function('Created app folder')
