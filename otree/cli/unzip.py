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
        # it's good to require this arg because then it's obvious that the files
        # will be put in that subfolder, and not dumped in the current dir
        parser.add_argument(
            'output_folder',
            type=str,
            nargs='?',
            help="What to call the new project folder",
        )

    def handle(self, zip_file, output_folder, **options):
        output_folder = output_folder or auto_named_output_folder(zip_file)
        unzip(zip_file, output_folder)
        msg = f'Unzipped file. Enter this:\n' f'cd {esc_fn(output_folder)}\n'

        logger.info(msg)


def esc_fn(fn):
    if ' ' in fn:
        return f'\"{fn}\"'
    return fn


def auto_named_output_folder(zip_file_name) -> str:
    default_folder_name = Path(zip_file_name).stem

    if not Path(default_folder_name).exists():
        return default_folder_name

    logger.info(
        'Hint: you can provide the name of the folder to create. Example:\n'
        f"otree unzip {esc_fn(zip_file_name)} my_project"
    )
    for x in range(2, 20):
        folder_name = f'{default_folder_name}-{x}'
        if not Path(folder_name).exists():
            return folder_name
    logger.error(
        f"Could not unzip the file; target folder {folder_name} already exists. "
    )
    sys.exit(-1)


def unzip(zip_file: str, output_folder):
    if os.path.isfile('settings.py') and os.path.isfile('manage.py'):
        logger.error(
            'You are trying to unzip a project but it seems you are '
            'already in a project folder (found settings.py and manage.py).'
        )
        sys.exit(-1)

    with tarfile.open(zip_file) as tar:
        def is_within_directory(directory, target):
            
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)
        
            prefix = os.path.commonprefix([abs_directory, abs_target])
            
            return prefix == abs_directory
        
        def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
        
            for member in tar.getmembers():
                member_path = os.path.join(path, member.name)
                if not is_within_directory(path, member_path):
                    raise Exception("Attempted Path Traversal in Tar File")
        
            tar.extractall(path, members, numeric_owner=numeric_owner) 
            
        
        safe_extract(tar, output_folder)
