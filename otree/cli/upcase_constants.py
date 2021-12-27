import re
from importlib import import_module
from pathlib import Path

"""Don't import from remove_self, because that requires rope to be installed."""
from otree.common import get_class_bounds
from otree.constants import BaseConstants
from .base import BaseCommand

print_function = print


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('apps', nargs='*')
        parser.add_argument(
            '--keep', action='store_true', dest='keep_old_files', default=False,
        )

    def handle(self, *args, apps, keep_old_files, **options):
        root = Path('.')
        for app in root.iterdir():
            init_path = app.joinpath('__init__.py')
            app_name = app.name
            if not init_path.exists():
                continue
            text = init_path.read_text('utf8')
            if 'class Constants(' not in text:
                print_function(f"Skipping {app_name}")
                continue
            text = text.replace('class Constants(', 'class C(')
            module = import_module(app_name)
            Constants = module.Constants
            classvars = [k for k in vars(Constants) if k not in vars(BaseConstants)]
            cls_start, cls_end = get_class_bounds(text, 'C')
            class_txt = text[cls_start:cls_end]
            for classvar in classvars:
                class_txt = re.sub(
                    r'\b' + classvar + r'\b', classvar.upper(), class_txt
                )
            final = text[:cls_start] + class_txt + text[cls_end:]
            init_path.write_text(final, encoding='utf8')

        files_to_replace = []
        # need to replace all files and templates, including in _templates folder.
        for glob in ['*.html', '*.py', '*/*.html', '*/*.py', '*/*/*.html', '*/*/*.py']:
            files_to_replace.extend(root.glob(glob))

        for p in files_to_replace:
            txt = p.read_text('utf8')
            # somehow \w also works with non-latin chars, nice
            txt = re.sub(r'\bConstants\.(\w+)\b', upcase, txt)
            p.write_text(txt, encoding='utf8')
        print_function("Done")


def upcase(match):
    upcased_name = match.group(1).upper()
    return f'C.{upcased_name}'
