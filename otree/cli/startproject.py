import os
import sys
import otree
from .base import BaseCommand
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
import random

print_function = print


def prompt_about_sample_games():
    '''for easy patching'''
    return input("Include sample games? (y or n): ")


class Command(BaseCommand):
    help = "Creates a new oTree project."

    def add_arguments(self, parser):
        parser.add_argument('name')
        # we need a CLI arg rather than a small function we can patch,
        # because our test launches this in a subprocess.
        parser.add_argument(
            '--noinput', action='store_false', dest='interactive', default=True,
        )

    def handle(self, name, interactive):
        dest = Path(name)
        if Path('settings.py').exists() and Path('manage.py').exists():
            msg = (
                'You are trying to create a project but it seems you are '
                'already in a project folder (found settings.py and manage.py).'
            )
            sys.exit(msg)
        if dest.exists():
            msg = (
                f'There is already a project called "{name}" '
                'in this folder. Either delete that folder first, or use a different name.'
            )
            sys.exit(msg)

        if interactive and prompt_about_sample_games().lower() == "y":
            download_from_github(dest)
        else:
            copy_project_template(dest)
        settings_path = dest.joinpath('settings.py')
        settings_path.write_text(
            settings_path.read_text().replace(
                "{{ secret_key }}", str(random.randint(10 ** 12, 10 ** 13))
            )
        )

        msg = (
            'Created project folder.\n'
            f'Enter "cd {name}" to move inside the project folder, '
            'then start the server with "otree devserver".'  #
        )
        print_function(msg)


def download_from_github(dest: Path):
    # expensive import
    from urllib.request import urlopen
    import zipfile

    resp = urlopen("https://github.com/oTree-org/oTree/archive/master.zip")
    f = BytesIO()
    f.write(resp.read())
    f.seek(0)
    with TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(f, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)
        shutil.move(Path(tmpdir, 'oTree-master'), dest)


def copy_project_template(dest: Path):
    src = Path(otree.__file__).parent / 'project_template'
    shutil.copytree(src, dest)
