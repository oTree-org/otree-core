import inspect
import os
from importlib import import_module
from pathlib import Path
import sys
from otree import common
from otree.api import BasePlayer, BaseGroup, BaseSubsession, Currency, WaitPage, Page
from otree import settings
from otree.common import get_pages_module, get_models_module
from collections import namedtuple

Error = namedtuple('Error', ['title', 'id'])
Warning = namedtuple('Warning', ['title', 'id'])

print_function = print


class AppCheckHelper:
    def __init__(self, app_name):
        self.app_name = app_name
        self.path = Path(app_name)
        self.errors = []
        self.warnings = []

    def add_error(self, title, numeric_id: int):
        self.errors.append(Error(title, id=numeric_id))

    def add_warning(self, title, numeric_id: int):
        self.warnings.append(Warning(title, id=numeric_id))

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


def files(helper: AppCheckHelper, app_name):
    # don't check pages.py because it might be views.py
    for fn in ['models.py']:
        if not helper.get_path(fn).exists():
            helper.add_error('No "%s" file found in app folder' % fn, numeric_id=102)

    templates_dir = helper.get_path('templates')
    if templates_dir.is_dir():
        # check for files in templates/, but not in templates/<label>
        misplaced_files = list(templates_dir.glob('*.html'))
        if misplaced_files:
            msg = (
                "Templates files in wrong folder"
                'Move template files from "{app}/templates/" '
                'to "{app}/templates/{app}" subfolder'.format(app=app_name)
            )
            helper.add_error(msg, numeric_id=103)

        all_subfolders = set(templates_dir.glob('*/'))
        correctly_named_subfolders = set(templates_dir.glob('{}/'.format(app_name)))
        other_subfolders = all_subfolders - correctly_named_subfolders
        if other_subfolders and not correctly_named_subfolders:
            msg = (
                "The 'templates' folder has a subfolder called '{}', "
                "but it should be renamed '{}' to match the name of the app. "
            ).format(other_subfolders.pop().name, app_name)
            helper.add_error(msg, numeric_id=104)


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

    player_columns = list(Player.__table__.columns)
    if any(f.name == 'payoff' for f in player_columns):
        msg = (
            'You must remove the field "payoff" from Player, '
            "because it is already defined on BasePlayer."
        )
        helper.add_error(msg, numeric_id=114)
    if any(f.name == 'role' for f in player_columns):
        msg = (
            'You must remove the field "role" from Player, '
            "because it is already defined on BasePlayer."
        )
        helper.add_error(msg, numeric_id=114)

    for Model in [Player, Group, Subsession]:
        for attr_name in dir(Model):
            if attr_name not in base_model_attrs[Model.__name__]:
                try:
                    attr_value = getattr(Model, attr_name)
                    _type = type(attr_value)
                except AttributeError:
                    # I got "The 'q_country' attribute can only be accessed
                    # from Player instances."
                    # can just filter/ignore these.
                    pass
                else:
                    if _type in model_field_substitutes.keys():
                        msg = (
                            'NonModelFieldAttr: '
                            '{model} has attribute "{attr}", which is not a model field, '
                            'and will therefore not be saved '
                            'to the database.'
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


def constants(helper: AppCheckHelper, app_name):
    if not helper.module_exists('models'):
        return

    models = get_models_module(app_name)

    if not hasattr(models, 'Constants'):
        helper.add_error('models.py does not contain Constants class', numeric_id=11)
        return

    Constants = models.Constants
    attrs = ['name_in_url', 'players_per_group', 'num_rounds']
    for attr_name in attrs:
        if not hasattr(Constants, attr_name):
            msg = "models.py: 'Constants' class needs to define '{}'"
            helper.add_error(msg.format(attr_name), numeric_id=12)
    ppg = Constants.players_per_group
    if ppg == 0 or ppg == 1:
        helper.add_error(
            "models.py: Constants.players_per_group cannot be {}. You "
            "should set it to None, which makes the group "
            "all players in the subsession.".format(ppg),
            numeric_id=13,
        )
    if ' ' in Constants.name_in_url:
        helper.add_error(
            "models.py: Constants.name_in_url must not contain spaces", numeric_id=14
        )


def pages_function(helper: AppCheckHelper, app_name):
    pages_module = common.get_pages_module(app_name)
    try:
        page_list = pages_module.page_sequence
    except:
        helper.add_error(
            'pages.py is missing the variable page_sequence.', numeric_id=21
        )
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
                            'You should instead define group_by_arrival_time_method on the Subsession. '
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
    for check_function in [model_classes, files, constants, pages_function]:
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
