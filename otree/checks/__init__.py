import glob
import inspect
import io
import os

from otree import common_internal
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.core.checks import register, Error, Warning
from django.template import Template
from django.template import TemplateSyntaxError

from otree.api import (
    BasePlayer, BaseGroup, BaseSubsession, Currency, WaitPage, Page)
from otree.common_internal import _get_all_configs


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





# CHECKS

def files(helper: AppCheckHelper, **kwargs):
    for fn in ['models.py']: # don't check views.py because it might be pages.py
        if not os.path.isfile(helper.get_path(fn)):
            helper.add_error(
                'NoModelsOrViews: No "%s" file found in game folder' % fn,
                numeric_id=102
            )

    if os.path.isdir(helper.get_path('templates')):

        # check for files in templates, but not in templates/<label>

        misplaced_templates = set(glob.glob(
            os.path.join(helper.get_path('templates'), '*.html')
        ))
        misplaced_templates.discard(helper.app_config.label)
        if misplaced_templates:
            hint = (
                'Move template files from "{app}/templates/" '
                'to "{app}/templates/{app}" subfolder'.format(
                    app=helper.app_config.label)
            )
            helper.add_error(
                "TemplatesInWrongDir: Templates files in app's root template folder",
                hint=hint, numeric_id=103,
            )


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
    type(None): 'IntegerField' # not always int, but it's a reasonable suggestion
}


def model_classes(helper: AppCheckHelper, **kwargs):

    for name in ['Subsession', 'Group', 'Player']:
        try:
            helper.app_config.get_model(name)
        except LookupError:
            helper.add_error(
                'MissingModel: Model "%s" not defined' % name, numeric_id=110)

    app_config = helper.app_config
    Player = app_config.get_model('Player')
    Group = app_config.get_model('Group')
    Subsession = app_config.get_model('Subsession')

    for Model in [Player, Group, Subsession]:
        for attr in dir(Model):
            if attr not in base_model_attrs[Model.__name__]:
                try:
                    _type = type(getattr(Model, attr))
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
                            'to the database.'.format(Model.__name__, attr))

                        helper.add_error(
                            msg,
                            numeric_id=111,
                            hint='Consider changing to "{} = models.{}(initial={})"'.format(
                                attr, model_field_substitutes[_type], repr(getattr(Model, attr)))
                        )
                    # if people just need an iterable of choices for a model field,
                    # they should use a tuple, not list or dict
                    if _type in {list, dict, set}:
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
                        ).format(ModelName=Model.__name__,
                                 attr=attr,
                                 type_name=_type.__name__)

                        helper.add_error(warning, numeric_id=112)


def constants(helper: AppCheckHelper, **kwargs):
    if not helper.module_exists('models'):
        return
    if not helper.class_exists('models', 'Constants'):
        helper.add_error(
            'models.py does not contain Constants class', numeric_id=11
        )
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
            "models.py: 'Constants.players_per_group' cannot be {}. You "
            "should set it to None, which makes the group "
            "all players in the subsession.".format(ppg),
            numeric_id=13
        )


def pages_function(helper: AppCheckHelper, **kwargs):
    views_module = common_internal.get_views_module(helper.app_config.name)
    views_or_pages = views_module.__name__.split('.')[-1]
    try:
        page_list = views_module.page_sequence
    except:
        helper.add_error(
            '{}.py is missing the variable page_sequence.'.format(views_or_pages),
            numeric_id=21
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
            # BUT: built-in Trust game has a wait page called WaitPage.
            # need to get rid of that first.
            if ViewCls.__name__ == 'Page':
                msg = (
                    "page_sequence cannot contain "
                    "a class called 'Page'. You should subclass Page "
                    "and give your page a different name."
                )
                helper.add_error(msg, numeric_id=22)
            if issubclass(ViewCls, WaitPage):
                if hasattr(ViewCls, 'before_next_page'):
                    helper.add_error(
                        '"{}" defines before_next_page, '
                        'which is not valid on wait pages.'.format(
                            ViewCls.__name__),
                        numeric_id=27
                    )
                if ViewCls.group_by_arrival_time:
                    if i > 0:
                        helper.add_error(
                            '"{}" has group_by_arrival_time=True, so '
                            'it must be placed first in page_sequence.'.format(
                                ViewCls.__name__), numeric_id=23)
                    if ViewCls.wait_for_all_groups:
                        helper.add_error(
                            '"{}" has group_by_arrival_time=True, so '
                            'it cannot have wait_for_all_groups=True also.'.format(
                                ViewCls.__name__), numeric_id=24)
                # alternative technique is to not define the method on WaitPage
                # and then use hasattr, but I want to keep all complexity
                # out of views.abstract
                elif (ViewCls.get_players_for_group != WaitPage.get_players_for_group):
                    helper.add_error(
                        '"{}" defines get_players_for_group, '
                        'but in order to use this method, you must set '
                        'group_by_arrival_time=True'.format(
                            ViewCls.__name__), numeric_id=25)
            elif issubclass(ViewCls, Page):
                pass # ok
            else:
                msg = '"{}" is not a valid page'.format(ViewCls)
                helper.add_error(msg, numeric_id=26)


def template_valid(template_name: str, helper: AppCheckHelper):
    from otree.checks.templates import get_unreachable_content
    from otree.checks.templates import has_valid_encoding
    from otree.checks.templates import format_source_snippet

    # Only test files that are valid templates.
    if not has_valid_encoding(template_name):
        return

    try:
        with io.open(template_name, 'r', encoding='utf8') as f:
            compiled_template = Template(f.read())
    except (IOError, OSError, TemplateSyntaxError):
        # When we used Django 1.8
        # we used to show the line from the source that caused the error,
        # but django_template_source was removed at some point,
        # so it's better to let the yellow error page show the error nicely
        return

    def format_content(text):
        text = text.strip()
        lines = text.splitlines()
        lines = ['> {0}'.format(line) for line in lines]
        return '\n'.join(lines)

    contents = get_unreachable_content(compiled_template)
    content_bits = '\n\n'.join(
        format_content(bit)
        for bit in contents)
    if contents:
        helper.add_error(
            'Template contains the following text outside of a '
            '{% block %}. This text will never be displayed.'
            '\n\n' + content_bits,
            obj=os.path.join(helper.app_config.label,
                             helper.get_rel_path(template_name)),
            numeric_id=7)


def templates_valid(helper: AppCheckHelper, **kwargs):
    for template_name in helper.get_template_names():
        template_valid(template_name, helper)

def unique_sessions_names(helper: AppCheckHelper, **kwargs):
    already_seen = set()
    for st in settings.SESSION_CONFIGS:
        st_name = st["name"]
        if st_name in already_seen:
            msg = "Duplicate SESSION_CONFIG name '{}'".format(st_name)
            helper.add_error(msg, numeric_id=40)
        else:
            already_seen.add(st_name)


def unique_room_names(helper: AppCheckHelper, **kwargs):
    already_seen = set()
    for room in getattr(settings, 'ROOMS', []):
        room_name = room["name"]
        if room_name in already_seen:
            msg = "Duplicate ROOM name '{}'".format(room_name)
            helper.add_error(msg, numeric_id=50)
        else:
            already_seen.add(room_name)


def template_encoding(helper: AppCheckHelper, **kwargs):
    from otree.checks.templates import has_valid_encoding
    for template_name in helper.get_template_names():
        if not has_valid_encoding(template_name):
            helper.add_error(
                'The template {template} is not UTF-8 encoded. '
                'Please configure your text editor to always save files '
                'as UTF-8. Then open the file and save it again.'
                .format(template=helper.get_rel_path(template_name)),
                numeric_id=60,
            )


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


def make_check_function_run_once(func):
    def check_function(app_configs, **kwargs):
        otree_app_config = apps.get_app_config('otree')
        #ignore app_configs list -- just run once
        errors = []
        helper = AppCheckHelper(otree_app_config, errors)
        func(helper, **kwargs)
        return errors

    return check_function


def register_system_checks():

    for func in [
        unique_room_names,
        unique_sessions_names,
    ]:
        check_function = make_check_function_run_once(func)
        register(check_function)

    for func in [
        model_classes,
        files,
        constants,
        pages_function,
        templates_valid,
        template_encoding,
    ]:
        check_function = make_check_function(func)
        register(check_function)
