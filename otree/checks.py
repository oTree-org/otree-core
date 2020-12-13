import inspect
import os
from importlib import import_module
from pathlib import Path

from django.core.checks import Error, Warning, register

from otree import common
from otree.api import BasePlayer, BaseGroup, BaseSubsession, Currency, WaitPage, Page
from otree.common import _get_all_configs


class AppCheckHelper:
    """Basically a wrapper around the AppConfig
    """

    def __init__(self, app_config, errors):
        self.app_config = app_config
        self.errors = errors

    def add_error(self, title, numeric_id: int, **kwargs):
        issue_id = 'otree.E' + str(numeric_id).zfill(3)
        kwargs.setdefault('obj', self.app_config.label)
        return self.errors.append(Error(title, id=issue_id, **kwargs))

    def add_warning(self, title, numeric_id: int, **kwargs):
        kwargs.setdefault('obj', self.app_config.label)
        issue_id = 'otree.W' + str(numeric_id).zfill(3)
        return self.errors.append(Warning(title, id=issue_id, **kwargs))

    # Helper meythods

    def get_path(self, name):
        return os.path.join(self.app_config.path, name)

    def get_rel_path(self, name):
        basepath = os.getcwd()
        return os.path.relpath(name, basepath)

    def get_module(self, name):
        return import_module(self.app_config.name + '.' + name)

    def get_template_names(self):
        path = self.get_path('templates')
        template_names = []
        for root, dirs, files in os.walk(path):
            for filename in [f for f in files if f.endswith('.html')]:
                template_names.append(os.path.join(root, filename))
        return template_names

    def module_exists(self, module):
        try:
            self.get_module(module)
            return True
        except ImportError as e:
            return False

    def class_exists(self, module, name):
        module = self.get_module(module)
        cls = getattr(module, name, None)
        return inspect.isclass(cls)


def files(helper: AppCheckHelper, **kwargs):
    # don't check views.py because it might be pages.py
    for fn in ['models.py']:
        if not os.path.isfile(helper.get_path(fn)):
            helper.add_error('No "%s" file found in app folder' % fn, numeric_id=102)

    templates_dir = Path(helper.get_path('templates'))
    app_label = helper.app_config.label
    if templates_dir.is_dir():
        # check for files in templates/, but not in templates/<label>
        misplaced_files = list(templates_dir.glob('*.html'))
        if misplaced_files:
            hint = (
                'Move template files from "{app}/templates/" '
                'to "{app}/templates/{app}" subfolder'.format(app=app_label)
            )

            helper.add_error(
                "Templates files in wrong folder", hint=hint, numeric_id=103
            )

        all_subfolders = set(templates_dir.glob('*/'))
        correctly_named_subfolders = set(templates_dir.glob('{}/'.format(app_label)))
        other_subfolders = all_subfolders - correctly_named_subfolders
        if other_subfolders and not correctly_named_subfolders:
            msg = (
                "The 'templates' folder has a subfolder called '{}', "
                "but it should be renamed '{}' to match the name of the app. "
            ).format(other_subfolders.pop().name, app_label)
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


def model_classes(helper: AppCheckHelper, **kwargs):
    for name in ['Subsession', 'Group', 'Player']:
        try:
            helper.app_config.get_model(name)
        except LookupError:
            helper.add_error(
                'MissingModel: Model "%s" not defined' % name, numeric_id=110
            )

    app_config = helper.app_config
    Player = app_config.get_model('Player')
    Group = app_config.get_model('Group')
    Subsession = app_config.get_model('Subsession')

    if hasattr(Subsession, 'before_session_starts'):
        msg = (
            'before_session_starts no longer exists. '
            "You should rename it to creating_session."
        )
        helper.add_error(msg, numeric_id=119)

    if any(f.name == 'payoff' for f in Player._meta.fields):
        msg = (
            'You must remove the field "payoff" from Player, '
            "because it is already defined on BasePlayer."
        )
        helper.add_error(msg, numeric_id=114)
    if any(f.name == 'role' for f in Player._meta.fields):
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
                            '{} has attribute "{}", which is not a model field, '
                            'and will therefore not be saved '
                            'to the database.'.format(Model.__name__, attr_name)
                        )

                        helper.add_error(
                            msg,
                            numeric_id=111,
                            hint='Consider changing to "{} = models.{}(initial={})"'.format(
                                attr_name,
                                model_field_substitutes[_type],
                                repr(getattr(Model, attr_name)),
                            ),
                        )
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


def constants(helper: AppCheckHelper, **kwargs):
    if not helper.module_exists('models'):
        return
    if not helper.class_exists('models', 'Constants'):
        helper.add_error('models.py does not contain Constants class', numeric_id=11)
        return

    models = helper.get_module('models')
    Constants = getattr(models, 'Constants')
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


def pages_function(helper: AppCheckHelper, **kwargs):
    pages_module = common.get_pages_module(helper.app_config.name)
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
            if ViewCls.__name__ == 'WaitPage' and helper.app_config.name != 'trust':
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


def make_check_function(func):
    def check_function(app_configs, **kwargs):
        # if app_configs list is given (e.g. otree check app1 app2), run on those
        # if it's None, run on all apps
        # (system check API requires this)
        app_configs = app_configs or _get_all_configs()
        errors = []
        for app_config in app_configs:
            helper = AppCheckHelper(app_config, errors)
            func(helper, **kwargs)
        return errors

    return check_function


def register_system_checks():
    for func in [model_classes, files, constants, pages_function]:
        check_function = make_check_function(func)
        register(check_function)
