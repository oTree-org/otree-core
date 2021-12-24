import inspect
import os
from importlib import import_module
from pathlib import Path
import sys
from otree import common
from otree.api import BasePlayer, BaseGroup, BaseSubsession, Currency, WaitPage, Page
from otree import settings
from otree.common import get_pages_module, get_models_module, get_builtin_constant
from collections import namedtuple

Error = namedtuple('Error', ['title', 'id', 'app_name',])
Warning = namedtuple('Warning', ['title', 'id', 'app_name'])

print_function = print


class AppCheckHelper:
    def __init__(self, app_name):
        self.app_name = app_name
        self.path = Path(app_name)
        self.errors = []
        self.warnings = []

    def add_error(self, title, numeric_id: int):
        self.errors.append(Error(title, id=numeric_id, app_name=self.app_name))

    def add_warning(self, title, numeric_id: int):
        self.warnings.append(Warning(title, id=numeric_id, app_name=self.app_name))

    def get_template_names(self):
        templates_dir = self.path / 'templates'
        for root, dirs, files in os.walk(templates_dir):
            for name in files:
                if name.endswith('.html'):
                    yield templates_dir.joinpath(root, name)

    def get_path(self, name):
        return self.path.joinpath(name)

    def module_exists(self, module):
        return self.path.joinpath(module + '.py').exists()


base_model_attrs = {
    'Player': set(dir(BasePlayer)),
    'Group': set(dir(BaseGroup)),
    'Subsession': set(dir(BaseSubsession)),
}
model_field_substitutes = {
    int: 'IntegerField',
    float: 'FloatField',
    bool: 'BooleanField',
    str: 'CharField',
    Currency: 'CurrencyField',
    type(None): 'IntegerField'
    # not always int, but it's a reasonable suggestion
}


def model_classes(helper: AppCheckHelper, app_name):
    models = get_models_module(app_name)
    for name in ['Subsession', 'Group', 'Player']:
        if not hasattr(models, name):
            helper.add_error(
                'MissingModel: Model "%s" not defined' % name, numeric_id=110
            )

    Player = models.Player
    Group = models.Group
    Subsession = models.Subsession

    if hasattr(Subsession, 'before_session_starts'):
        msg = (
            'before_session_starts no longer exists. '
            "You should rename it to creating_session."
        )
        helper.add_error(msg, numeric_id=119)

    for Model in [Player, Group, Subsession]:
        for attr_name in dir(Model):
            if attr_name not in base_model_attrs[Model.__name__]:
                attr_value = getattr(Model, attr_name)
                _type = type(attr_value)
                if _type in model_field_substitutes.keys():
                    msg = (
                        'NonModelFieldAttr: '
                        '{model} has attribute "{attr}", which is not a model field, '
                        'and will therefore not be saved '
                        'to the database. '
                        'Consider changing to "{attr} = models.{FieldType}(initial={attr_value})"'
                    ).format(
                        model=Model.__name__,
                        attr=attr_name,
                        FieldType=model_field_substitutes[_type],
                        attr_value=repr(attr_value),
                    )
                    helper.add_error(msg, numeric_id=111)

                # if people just need an iterable of choices for a model field,
                # they should use a tuple, not list or dict
                elif _type in {list, dict, set}:
                    warning = (
                        'MutableModelClassAttr: '
                        '{ModelName}.{attr} is a {type_name}. '
                        'Modifying it during a session (e.g. appending or setting values) '
                        'will have unpredictable results; '
                        'you should use '
                        'session.vars or participant.vars instead. '
                        'Or, if this {type_name} is read-only, '
                        "then it's recommended to move it outside of this class "
                        '(e.g. put it in Constants).'
                    ).format(
                        ModelName=Model.__name__,
                        attr=attr_name,
                        type_name=_type.__name__,
                    )

                    helper.add_error(warning, numeric_id=112)


def is_builtin(func_name):
    if func_name in [
        'creating_session',
        'custom_export',
        'group_by_arrival_time_method',
        'vars_for_admin_report',
    ]:
        return True
    endings = ['_min', '_max', '_choices', '_error_message']
    for ending in endings:
        if func_name.endswith(ending):
            return True
    return False


def uncalled_functions(helper: AppCheckHelper, app_name):
    import re

    if not common.is_noself(app_name):
        return

    txt = Path(f'{app_name}/__init__.py').read_text('utf8')
    for match in re.finditer(r'def (\w+)\(', txt):
        func_name = match.group(1)
        if is_builtin(func_name):
            continue
        # hasattr( is a double-check in case the function is commented out
        # it's also ok if the function is used as as method, e.g. oTree Studio.
        # also, some functions are assigned as variables, e.g. is_displayed = is_displayed
        if txt.count(func_name) == 1:
            app = import_module(app_name)
            if hasattr(app, func_name):
                msg = f"'{func_name}' is defined but not used"
                helper.add_warning(msg, numeric_id=131)


def constants(helper: AppCheckHelper, app_name):

    models = get_models_module(app_name)

    if not hasattr(models, 'Constants') and not hasattr(models, 'C'):
        helper.add_error('App is missing a constants class', numeric_id=11)
        return

    attrs = ['name_in_url', 'players_per_group', 'num_rounds']
    for attr_name in attrs:
        try:
            get_builtin_constant(app_name, attr_name)
        except AttributeError:
            msg = "Constants class needs to define '{}'".format(attr_name)
            helper.add_error(msg.format(attr_name), numeric_id=12)
    ppg = get_builtin_constant(app_name, 'players_per_group')
    if ppg == 0 or ppg == 1:
        helper.add_error(
            "players_per_group cannot be {}. You "
            "should set it to None, which makes the group "
            "all players in the subsession.".format(ppg),
            numeric_id=13,
        )
    if ' ' in get_builtin_constant(app_name, 'name_in_url'):
        helper.add_error("name_in_url must not contain spaces", numeric_id=14)


def pages_function(helper: AppCheckHelper, app_name):
    pages_module = common.get_pages_module(app_name)
    try:
        page_list = pages_module.page_sequence
    except:
        helper.add_error('The variable page_sequence is missing.', numeric_id=21)
        return
    else:
        for i, ViewCls in enumerate(page_list):
            # there is no good reason to include Page in page_sequence.
            # As for WaitPage: even though it works fine currently
            # and can save the effort of subclassing,
            # we should restrict it, because:
            # - one user had "class WaitPage(Page):".
            # - if someone makes "class WaitPage(WaitPage):", they might
            #   not realize why it's inheriting the extra behavior.
            # overall, I think the small inconvenience of having to subclass
            # once per app
            # is outweighed by the unexpected behavior if someone subclasses
            # it without understanding inheritance.
            # BUT: built-in Trust game had a wait page called WaitPage.
            # that was fixed on Aug 24, 2017, need to wait a while...
            # see below in ensure_no_misspelled_attributes,
            # we can get rid of a check there also
            if ViewCls.__name__ == 'Page':
                msg = "page_sequence cannot contain a class called 'Page'."
                helper.add_error(msg, numeric_id=22)
            if ViewCls.__name__ == 'WaitPage' and app_name != 'trust':
                msg = "page_sequence cannot contain a class called 'WaitPage'."
                helper.add_error(msg, numeric_id=221)

            if issubclass(ViewCls, WaitPage):
                if ViewCls.group_by_arrival_time:
                    if i > 0:
                        helper.add_error(
                            '"{}" has group_by_arrival_time=True, so '
                            'it must be placed first in page_sequence.'.format(
                                ViewCls.__name__
                            ),
                            numeric_id=23,
                        )
                    if ViewCls.wait_for_all_groups:
                        helper.add_error(
                            'Page "{}" has group_by_arrival_time=True, so '
                            'it cannot have wait_for_all_groups=True also.'.format(
                                ViewCls.__name__
                            ),
                            numeric_id=24,
                        )
                    if hasattr(ViewCls, 'get_players_for_group'):
                        helper.add_error(
                            'Page "{}" defines get_players_for_group, which is deprecated. '
                            'You should instead define a top-level function called group_by_arrival_time_method. '
                            ''.format(ViewCls.__name__),
                            numeric_id=25,
                        )
            elif issubclass(ViewCls, Page):
                pass  # ok
            else:
                msg = '"{}" is not a valid page'.format(ViewCls)
                helper.add_error(msg, numeric_id=26)


def get_checks_output(app_names=None):
    app_names = app_names or settings.OTREE_APPS
    errors = []
    warnings = []
    for check_function in [
        model_classes,
        constants,
        pages_function,
        uncalled_functions,
    ]:
        for app_name in app_names:
            helper = AppCheckHelper(app_name)
            check_function(helper, app_name)
            errors.extend(helper.errors)
            warnings.extend(helper.warnings)
    return errors, warnings


def run_checks():
    errors, warnings = get_checks_output()
    if errors:
        for ele in errors:
            print_function(ele)
        sys.exit(-1)
    for ele in warnings:
        print_function(ele)
