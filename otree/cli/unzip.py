from .base import BaseCommand
import tarfile
import logging
import os.path
import sys
from pathlib import Path

print_function = print

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Unzip a zipped oTree project"

    def add_arguments(self, parser):
        parser.add_argument('zip_file', type=str, help="The .otreezip file")

    def handle(self, zip_file):
        output_folder = Path(zip_file).stem

        if Path(output_folder).exists():
            sys.exit(
                f"Could not unzip the file; target folder '{output_folder}' already exists. "
            )

        unzip(zip_file, output_folder)
        msg = f'Unzipped file. Enter this:\n' f'cd {esc_fn(output_folder)}\n'

        logger.info(msg)


def esc_fn(fn):
    if ' ' in fn:
        return f'\"{fn}\"'
    return fn


def unzip(zip_file: str, output_folder):
    if os.path.isfile('settings.py'):
        logger.error(
            'You are trying to unzip a project but it seems you are '
            'already in a project folder (found settings.py).'
        )
        sys.exit(-1)

    with tarfile.open(zip_file) as tar:
        tar.extractall(output_folder)
