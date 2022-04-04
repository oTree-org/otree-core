import os
import re
import shutil
from pathlib import Path
from typing import List, Tuple

from .base import BaseCommand
from ..common import get_class_bounds

try:

    import rope.base.codeanalyze
    import rope.refactor.occurrences
    from rope.refactor import rename, move
    from rope.refactor.rename import Rename
    from rope.base.project import Project
    from rope.base.libutils import path_to_resource
    import black
except ModuleNotFoundError:
    import sys

    sys.exit(
        'Before running this command, you need to run "pip3 install -U rope black==20.8b1" '
    )
from rope.refactor.importutils import ImportTools
from collections import namedtuple
from typing import Iterable

print_function = print

MethodInfo = namedtuple('MethodInfo', ['start', 'stop', 'name', 'model'])


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('apps', nargs='*')
        parser.add_argument(
            '--keep', action='store_true', dest='keep_old_files', default=False,
        )

    def handle(self, *args, apps, keep_old_files, **options):
        for app in Path('.').iterdir():
            if app.joinpath('models.py').exists():
                app_name = app.name
                if apps and app_name not in apps:
                    continue
                if not keep_old_files:
                    backup(app_name)
                try:
                    make_noself(app_name)
                except Exception as exc:
                    app.joinpath('__init__.py').write_text('')
                    raise
                if not keep_old_files:
                    rearrange_folder(app_name)
            # convert app.py format
            elif app.joinpath('app.py').exists():
                init = app.joinpath('__init__.py')
                init.unlink(missing_ok=True)
                app.joinpath('app.py').rename(init)
        # delete manage.py so that PyCharm doesn't try to enforce Django syntax in templates
        manage_py = Path('manage.py')
        if manage_py.exists():
            manage_py.unlink()

        print_function('Done. You should also run: otree upcase_constants')


class CannotConvert(Exception):
    pass


CURRENCY_C_IMPORT = 'Currency as c'


def make_noself(app_name):
    proj = Project(app_name, ropefolder=None)
    approot = Path(app_name)
    app_path = approot / '__init__.py'
    pages_path = approot / 'pages.py'
    models_path = approot / 'models.py'
    if not models_path.exists():
        return
    print_function('Upgrading', app_name)

    def read():
        return app_path.read_text('utf8')

    def write(txt):
        app_path.write_text(txt, encoding='utf8')

    def writelines(lines):
        write('\n'.join(lines))

    END_OF_MODELS = '"""endofmodels"""'
    lines = [
        # 2021-12-25: don't know why this is here
        'from otree.api import Page, WaitPage',
        'from otree.api import *',
        # for some reason rope considers this a duplicate import
        'from otree.api import Currency as c',
        *models_path.read_text('utf8').splitlines(),
        END_OF_MODELS,
    ]

    pages_txt = pages_path.read_text('utf8')

    m = re.search(
        r'self\.(?!player|group|subsession|participant|session|timeout_happened|round_number)(\w+)',
        pages_txt,
    )
    if m:
        msg = f"""{app_name}/pages.py contains "{m.group(0)}". This is not a recognized page attribute."""
        raise CannotConvert(msg)

    for line in pages_txt.split('\n'):
        if line.startswith('from ._builtin'):
            continue
        if line.startswith('from .models'):
            continue

        lines.append(line)

    writelines(lines)

    # normalize, get rid of empty lines
    lines = app_path.read_text('utf8').splitlines(keepends=False)
    writelines(e.replace('\t', ' ' * 4) for e in lines if e.strip())

    def resource(pth):
        return path_to_resource(proj, app_name + '/' + pth)

    app_res = resource('__init__.py')

    app_txt = read()

    # need it to be reversed so we don't shift everything down
    class_names = list(
        (m.group(1), m.group(2))
        for m in re.finditer(
            r'^class (\w+)\((BasePlayer|BaseGroup|BaseSubsession|Page|WaitPage)',
            app_txt,
            re.MULTILINE,
        )
    )

    model_methods = set()
    for class_name, base_class in reversed(class_names):
        offsets = get_method_offsets(app_txt, class_name)
        for offset, name in reversed(offsets):
            if base_class == 'WaitPage' and name == 'after_all_players_arrive':
                cls_start, cls_end = get_class_bounds(app_txt, class_name)
                is_subsession = (
                    'wait_for_all_groups = True' in app_txt[cls_start:cls_end]
                )
                rename_self_to = 'subsession' if is_subsession else 'group'
            else:
                rename_self_to = dict(
                    Player='player', Group='group', Subsession='subsession'
                ).get(class_name, 'player')
            # it might be error_message or app_after_this_page, which take extra args.
            self_offset = offset + app_txt[offset:].index('(self') + 2
            try:
                changes = Rename(proj, app_res, self_offset).get_changes(rename_self_to)
                proj.do(changes)
            except Exception:
                print_function(app_txt[self_offset : self_offset + 30])
                raise
            if class_name in ['Player', 'Group', 'Subsession']:
                model_methods.add(name)
                template_usage = f'{rename_self_to}.{name}'
                for tpl in approot.joinpath('templates', app_name).glob('*.html'):
                    if template_usage in tpl.read_text('utf8'):
                        print_function(
                            f"""
((((((((((((((((((((((((((((((
"{tpl}" contains the method call {template_usage}, but {name} has been converted to a function.
You have 2 choices:
\t(a) call {name}({rename_self_to}) in vars_for_template
\t(b) manually convert {name} back to a method
))))))))))))))))))))))))))))))"""
                        )

    app_txt = read()

    try:
        currency_offset = app_txt.index(CURRENCY_C_IMPORT)
    except ValueError:
        pass
    else:
        changes = Rename(
            proj, app_res, currency_offset + len(CURRENCY_C_IMPORT) - 1
        ).get_changes('cu')
        proj.do(changes)

    import_tools = ImportTools(proj)

    rope_module = proj.get_module('__init__')
    module_with_imports = import_tools.module_imports(rope_module)
    module_with_imports.remove_duplicates()
    module_with_imports.sort_imports()
    write(module_with_imports.get_changed_source())

    app_txt = read()
    lines = app_txt.splitlines()

    method_bounds = []
    for class_name, _ in class_names:
        if class_name in ['Player', 'Group', 'Subsession']:
            # print_function(ClassName, list(get_method_bounds(lines, ClassName)))
            method_bounds.extend(get_method_bounds(lines, class_name, start_index=0))
        else:
            for start, end, name, _ in reversed(
                list(get_method_bounds(lines, class_name, start_index=0))
            ):
                lines.insert(start, f'    @staticmethod')

    # return
    function_lines = ['# FUNCTIONS']
    non_function_lines = []

    i = 0
    for bound in method_bounds:
        non_function_lines.extend(lines[i : bound.start])
        function_lines.extend(
            dedent(line) for line in lines[bound.start : bound.stop + 1]
        )
        i = bound.stop + 1
    non_function_lines.extend(lines[i:])

    # not aapa, since we need to resolve it being defined on group vs subsession.
    for i, line in enumerate(non_function_lines):
        non_function_lines[i] = re.sub(
            r"""(live_method) = ["'](\w+)["']""", r'\1 = \2', line,
        )

    function_lines.append('# PAGES')
    function_txt = '\n'.join(function_lines)

    txt = '\n'.join(non_function_lines).replace(END_OF_MODELS, function_txt)

    txt = re.sub(r'\bplayer\.player\b', 'player', txt)
    # for AAPA

    txt = re.sub(r'\bgroup\.group\b', 'group', txt)
    txt = re.sub(r'\bsubsession\.subsession\b', 'subsession', txt)

    txt = txt.replace(
        'def before_next_page(player):',
        'def before_next_page(player, timeout_happened):',
    ).replace('player.timeout_happened', 'timeout_happened')

    # add type annotations
    # some functions have multiple args, like error_message
    txt = re.sub(r'def (\w+)\(player\b', r'def \1(player: Player', txt)
    txt = re.sub(r'def (\w+)\(group\b', r'def \1(group: Group', txt)
    txt = re.sub(r'def (\w+)\(subsession\b', r'def \1(subsession: Subsession', txt)

    txt = fix_method_calls(txt, model_methods)

    lines = txt.splitlines(keepends=False)

    # add missing 'pass' for empty classes
    lines2 = []
    for i in range(len(lines)):
        lines2.append(lines[i])
        # this will fail if the class only contains comments, but i don't see any easy solution for that.
        if lines[i].startswith('class ') and not lines[i + 1].startswith(' '):
            lines2.append(' ' * 4 + 'pass')

    write(black_format('\n'.join(lines2)))

    tests_path = approot.joinpath('tests.py')
    if tests_path.exists():

        tests_txt = tests_path.read_text('utf8')
        new_txt = (
            tests_txt.replace('from ._builtin import Bot', 'from otree.api import Bot')
            .replace('from . import pages', 'from . import *')
            .replace('from .models import Constants', '')
        )
        new_txt = re.sub(r'\bpages\.(\w)', r'\1', new_txt)
        approot.joinpath('tests_noself.py').write_text(new_txt, encoding='utf8')


def fix_method_calls(txt, model_methods):
    """this doesn't work for functions that take args. too complicated."""
    # change player.group.my_method() to my_method(player.group)
    def repl(m):
        if m.group(3) in model_methods:
            return m.group(3) + '(' + m.group(1) + m.group(2) + ')'
        return m.group()

    return re.sub(r'([\.\w]*)\b(player|group|subsession)\.(\w+)\(\)', repl, txt)


def dedent(line):
    if line.startswith(' ' * 4):
        return line[4:]
    return line


def black_format(txt):
    return black.format_str(
        txt, mode=black.Mode(line_length=100, string_normalization=False)
    )


def is_within_a_bound(bounds, lineno):
    for bound in bounds:
        if bound.start <= lineno <= bound.stop:
            return True


def get_method_bounds(lines, ModelName, start_index=1) -> Iterable[MethodInfo]:
    """1 based"""
    in_model = False

    start = None
    name = None
    model = None
    # use start=1 to match line numbers in text editor
    for lineno, line in enumerate(lines, start=start_index):
        if line.startswith(f'class {ModelName}('):
            in_model = True
            continue

        if in_model:

            if is_class_or_module_level_statement(line):
                if start:
                    yield MethodInfo(start, lineno - 1, name, model)
                    start = None
                if line.startswith('    def '):
                    start = lineno
                    m = re.search(r'def (\w+)\((\w+)', line)
                    name = m.group(1)
                    model = m.group(2)

            if is_module_level_statement(line):
                return


def is_class_or_module_level_statement(line):
    return line[:5].strip() and not line[:5].strip().startswith('#')


def is_module_level_statement(line):
    return line[:1].strip() and not line[:1].strip().startswith('#')


def get_method_offsets(txt, ClassName) -> List[Tuple[int, str]]:
    class_start, class_end = get_class_bounds(txt, ClassName)
    return [
        (m.start(), m.group(1))
        for m in re.finditer(r'^\s{4}def (\w+)\(self\b', txt, re.MULTILINE)
        if class_start < m.start() < class_end
    ]


BACKUP_FOLDER = '_REMOVE_SELF_BACKUP'


def backup(app_name):
    approot = Path(app_name)
    old_folder = Path(BACKUP_FOLDER)
    if not old_folder.exists():
        old_folder.mkdir()
    app_backup_dest = old_folder.joinpath(app_name)
    if not app_backup_dest.exists():
        shutil.copytree(approot, app_backup_dest)
    print_function(f'Your old files were saved to {BACKUP_FOLDER}/.')


def rearrange_folder(app_name):
    approot = Path(app_name)
    app_path = approot / '__init__.py'
    if not 'from otree.api' in app_path.read_text('utf8'):
        return
    print_function('Removing old files from', app_name)
    pages_path = approot / 'pages.py'
    models_path = approot / 'models.py'
    app_py_path = approot / 'app.py'
    if pages_path.exists():
        pages_path.unlink()
    if models_path.exists():
        models_path.unlink()
    if app_py_path.exists():
        app_py_path.unlink()
    _builtin = approot.joinpath('_builtin')
    if _builtin.exists():
        shutil.rmtree(_builtin)
    templates = approot.joinpath('templates', app_name)
    if templates.exists():
        copytree_py37_compat(templates, approot)
        shutil.rmtree(approot.joinpath('templates'))
    tests_noself = approot.joinpath('tests_noself.py')
    tests_path = approot.joinpath('tests.py')
    if tests_noself.exists():
        if tests_path.exists():
            tests_path.unlink()
        tests_noself.rename(tests_path)


def copytree_py37_compat(src, dst, symlinks=False, ignore=None):
    """replacement for shutil.copytree(templates, approot, dirs_exist_ok=True)"""
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)
