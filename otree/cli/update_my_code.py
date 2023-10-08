from pathlib import Path

import otree
from .base import BaseCommand

item_index = 1

NEW_MODELS_PY_IMPORTS = """
from otree.api import *
c = cu
from otree.api import (
    models,
    widgets,
    BaseConstants,
    BaseSubsession,
    BaseGroup,
    BasePlayer,
    Currency as c,
    currency_range,
)
"""

NEW_PAGES_PY_IMPORTS = """
from otree.api import Currency as c, currency_range
from ._builtin import Page, WaitPage
from .models import Constants
"""


print_function = print


def print_numbered(txt):
    global item_index
    print_function(f'\t{item_index}. {txt}')
    item_index += 1


class Command(BaseCommand):
    something_changed = False

    def handle(self, *args, **options):
        for msg in scan():
            print_numbered(msg)


def scan():
    root = Path('.')

    # old format imported otree.test and otree.views, so we need to get rid of it
    _builtins = root.glob('*/_builtin/__init__.py')
    for pth in _builtins:
        if 'z_autocomplete' in pth.read_text():
            new_text = (
                Path(otree.__file__)
                .parent.joinpath('app_template/_builtin/__init__.py')
                .read_text()
            )
            pth.write_text(new_text)

    settings_py = Path('settings.py').read_text('utf8')
    for substring in [
        'import otree.settings',
        'otree.settings.augment_settings(globals())',
        'from boto.mturk import qualification',
        'import dj_database_url',
    ]:
        if substring in settings_py:
            yield (
                f'Your settings.py contains "{substring}". You should delete this line.'
            )

    if 'DATABASES = {' in settings_py:
        yield ('settings.py contains a DATABASES setting. you should delete it.')

    for pth in root.glob('*/models.py'):
        txt = pth.read_text('utf8')
        if 'widgets.Slider' in txt:
            yield (
                f'{pth} uses widgets.Slider. This widget has been removed from oTree. '
                'You should instead remove this widget and use an <input type="range"> in the template (see the docs).'
            )
        if 'models.DecimalField' in txt:
            yield (
                f'{pth} uses models.DecimalField. You should use models.FloatField instead. '
            )
        if 'subsession = models.ForeignKey(Subsession)' in txt:
            yield (
                f'{pth} uses models.ForeignKey. You should delete all foreign keys. '
            )

        substrings = [
            'from otree.common',
            'from otree.constants',
            'from otree.models',
            'from otree.db',
        ]

        if any(substring in txt for substring in substrings):
            yield (
                f'{pth} imports non-API modules from otree. '
                f'You should change the lines at the top to:\n{NEW_MODELS_PY_IMPORTS}'
            )

    for views_py in root.glob('*/views.py'):
        pages_py = views_py.parent.joinpath('pages.py')
        if not pages_py.exists():
            views_py.rename(pages_py)
            print_function('AUTOMATIC: renamed views.py to pages.py')

    base_html = Path('_templates/global/Base.html')
    page_html = Path('_templates/global/Page.html')
    if base_html.exists() and not page_html.exists():
        base_html.rename(page_html)
        print_function('AUTOMATIC: renamed global/Base.html to global/Page.html')

    for pth in root.glob('*/pages.py'):
        txt = pth.read_text('utf8')

        if 'form_model = models.Player' in txt:
            yield (
                f"""In {pth}, you should change:\nform_model = models.Player\nto:\nform_model = 'player'"""
            )
        if 'form_model = models.Group' in txt:
            yield (
                f"""In {pth}, you should change:\nform_model = models.Group\nto:\nform_model = 'group'"""
            )

        substrings = [
            'from otree.common',
            'from otree.constants',
            'from otree.models',
            'from otree.db',
        ]

        if any(substring in txt for substring in substrings):
            yield (
                f'{pth} imports non-API modules from otree. '
                f'You should change the lines at the top to:\n{NEW_PAGES_PY_IMPORTS}'
            )

        if 'vars_for_all_templates' in txt:
            yield f'{pth}: {VARS_FOR_ALL_TEMPLATES_MSG}'

        for substring in ['min', 'max', 'choices', 'error_message']:
            if f'_{substring}(' in txt:
                yield (
                    f"{pth} contains a field validation function (FIELD_{substring}). "
                    "This function should be moved to models.py. See here: "
                    "https://otree.readthedocs.io/en/self/misc/version_history.html#new-format-for-form-validation"
                )

    for pth in root.glob('*/templates/*/*.html'):
        txt = pth.read_text('utf8')
        if '{% extends "global/Base.html" %}' in txt:
            yield (
                f'{pth} ' + 'starts with {% extends "global/Base.html" %}. '
                'You should remove that.'
            )
        if 'with label=' in txt:
            yield (
                str(pth)
                + ': the formfield tag should not use "with label=". Just change it to "label=" '
            )
        if '|floatformat' in txt:
            yield (
                str(pth)
                + ': |floatformat is not available because it comes from Django. '
                'You should replace it with to0/to1/to2, for example {{ my_number|to2 }}'
            )
        for attr in ['toggle', 'target', 'parent', 'show']:
            oldstyle = 'data-' + attr
            newstyle = 'data-bs-' + attr
            if oldstyle in txt:
                yield (
                    str(pth)
                    + f': In Bootstrap 5, {oldstyle} has been renamed to {newstyle}.'
                )

    custom_css_pth = Path('_static/global/custom.css')
    if custom_css_pth.exists():
        for line in custom_css_pth.open(encoding='utf8'):
            if line.startswith('input {'):
                yield (
                    f'{custom_css_pth}: you should delete the styling for "input" (or just delete all file contents)'
                )

    print_function(DONE_MSG)


DONE_MSG = """
Done. all files checked.
(If you want, you can also run "otree remove_self" to switch to the new 'no self' format) 
"""

VARS_FOR_ALL_TEMPLATES_MSG = """
****************************************************************************************************************
* vars_for_all_templates() will not be called automatically. You should rename it to something like "shared_vars", 
* then call it from each page's vars_for_template. For example:
*
* def vars_for_template(self):
*    return shared_vars(self)
*    
* def vars_for_template(self):
*    # combine it with the page's vars
*    return {'a': 1, 'b': 2, **shared_vars(self)}
****************************************************************************************************************
"""
