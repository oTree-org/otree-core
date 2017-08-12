#!/usr/bin/env python
# -*- coding: utf-8 -*-

import glob
import inspect
import io
import os
import types
from functools import wraps
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.core.checks import register, Error, Warning
from django.template import Template
from django.template import TemplateSyntaxError

import otree.views.abstract
from otree.api import BasePlayer, BaseGroup, BaseSubsession, Currency
from otree.common_internal import _get_all_configs


class Rules(object):
    """A helper class incapsulating common checks.

    Usage:
        rules = Rules(app_config, errors_list)

        # various rule checks, see below for list of rules
        rules.file_exists('some_file.py')
        ...

        # custom checks
        if <your-condition>:
            rules.push_error('...', id='...')

        # using checks as guards
        if rules.module_exists('tests'):
            tests = rules.get_module('tests') # won't fail
            ...

    """

    common_buffer = {}

    def __init__(self, config, errors, id=None):
        self.config = config
        self.errors = errors
        self.id = id

    def rule(meth):
        '''
        wrapper to return True if the method doesn't return anything.
        and False if it does return something.
        '''
        @wraps(meth)
        def wrapper(self, *args, **kwargs):
            res = meth(self, *args, **kwargs)
            if res:
                self.errors.append(res)
                return False
            else:
                return True
        return wrapper

    def error(self, title, **kwargs):
        kwargs.setdefault('obj', self.config.label)
        kwargs.setdefault('id', self.id)
        return Error(title, **kwargs)

    def push_error(self, title, **kwargs):
        return self.errors.append(self.error(title, **kwargs))

    def warning(self, title, **kwargs):
        kwargs.setdefault('obj', self.config.label)
        kwargs.setdefault('id', self.id)
        return Warning(title, **kwargs)

    def push_warning(self, title, **kwargs):
        return self.errors.append(self.warning(title, **kwargs))

    # Helper meythods

    def get_path(self, name):
        return os.path.join(self.config.path, name)

    def get_rel_path(self, name):
        basepath = os.getcwd()
        return os.path.relpath(name, basepath)

    def get_module(self, name):
        return import_module(self.config.name + '.' + name)

    def get_module_attr(self, module, name):
        if not isinstance(module, types.ModuleType):
            module = self.get_module(module)
        return getattr(module, name)

    def get_template_names(self):
        path = self.get_path('templates')
        template_names = []
        for root, dirs, files in os.walk(path):
            for filename in [f for f in files if f.endswith('.html')]:
                template_names.append(os.path.join(root, filename))
        return template_names

    # Rule methods

    @rule
    def file_exists(self, filename):
        if not os.path.isfile(self.get_path(filename)):
            return self.error('No "%s" file found in game folder' % filename)

    @rule
    def dir_exists(self, filename):
        if not os.path.isdir(self.get_path(filename)):
            msg = 'No "%s" directory found in game folder' % filename
            return self.error(msg)

    @rule
    def model_exists(self, name):
        try:
            self.config.get_model(name)
        except LookupError:
            return self.error('Model "%s" not defined' % name)

    @rule
    def module_exists(self, module):
        try:
            module = self.get_module(module)
        except ImportError as e:
            return self.error('Can\'t import module "%s": %s' % (module, e))

    @rule
    def class_exists(self, module, name):
        module = self.get_module(module)
        cls = getattr(module, name, None)
        if not inspect.isclass(cls):
            msg = 'No class "%s" in module "%s"' % (name, module.__name__)
            return self.error(msg)

    @rule
    def template_has_valid_syntax(self, template_name):
        from otree.checks.templates import has_valid_encoding
        from otree.checks.templates import format_source_snippet

        # Only test files that are valid templates.
        if not has_valid_encoding(template_name):
            return

        try:
            with io.open(template_name, 'r', encoding='utf8') as f:
                Template(f.read())
        except (IOError, OSError):
            pass
        except TemplateSyntaxError as error:
            # The django_template_source attribute will only be available on
            # DEBUG = True.
            if hasattr(error, 'django_template_source'):
                template_source, position = error.django_template_source
                snippet = format_source_snippet(
                    template_source.source,
                    arrow_position=position[0])
                message = (
                    'Template syntax error in {template}\n'
                    '\n'
                    '{snippet}\n'
                    '\n'
                    'Error: {error}'.format(
                        template=template_name,
                        error=error,
                        snippet=snippet))
            else:
                message = (
                    'Template syntax error in {template}\n'
                    'Error: {error}\n'
                    'Set "DEBUG = True" to see more details.'.format(
                        template=template_name, error=error))
            return self.error(message)

    @rule
    def template_has_no_dead_code(self, template_name):
        from otree.checks.templates import get_unreachable_content
        from otree.checks.templates import has_valid_encoding

        # Only test files that are valid templates.
        if not has_valid_encoding(template_name):
            return

        try:
            with io.open(template_name, 'r', encoding='utf8') as f:
                compiled_template = Template(f.read())
        except (IOError, OSError, TemplateSyntaxError):
            # Ignore errors that occured during file-read or compilation.
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
            return self.error(
                'Template contains the following text outside of a '
                '{% block %}. This text will never be displayed.'
                '\n\n' + content_bits,
                obj=os.path.join(self.config.label,
                                 self.get_rel_path(template_name)))

    @rule
    def template_has_valid_encoding(self, template_name):
        from otree.checks.templates import has_valid_encoding

        if not has_valid_encoding(template_name):
            return self.error(
                'The template {template} is not UTF-8 encoded. '
                'Please configure your text editor to always save files '
                'as UTF-8. Then open the file and save it again.'
                .format(template=self.get_rel_path(template_name)))


def register_rules(tags=(), id=None, once_per_project=False):
    """Transform a function based on rules, to a something
    django.core.checks.register takes.
    Passes Rules instance as first argument.
    """
    def decorator(func):
        @register(*tags)
        @wraps(func)
        def wrapper(app_configs, **kwargs):
            if once_per_project:
                # some checks should only be run once, not for each app
                app_configs = [apps.get_app_config('otree')]
            else:
                # if app_configs list is given (e.g. otree check app1 app2), run on those
                # if it's None, run on all apps
                # (system check API requires this)
                app_configs = app_configs or _get_all_configs()
            errors = []
            for config in app_configs:
                rules = Rules(config, errors, id=id)
                func(rules, **kwargs)
            return errors
        return wrapper
    return decorator


# Checks
@register_rules(id='otree.E001')
def files(rules, **kwargs):
    rules.file_exists('models.py')
    rules.file_exists('views.py')

    if os.path.isdir(rules.get_path('templates')):
        # check for files in templates, but not in templates/<label>
        misplaced_templates = set(glob.glob(
            os.path.join(rules.get_path('templates'), '*.html')
        ))
        misplaced_templates.discard(rules.config.label)
        if misplaced_templates:
            hint = (
                'Move template files from "{app}/templates/" '
                'to "{app}/templates/{app}" subfolder'.format(
                    app=rules.config.label)
            )
            rules.push_error(
                "Templates files in app's root template directory",
                hint=hint, id='otree.E001'
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
    Currency: 'CurrencyField'
}


@register_rules(id='otree.E002')
def model_classes(rules, **kwargs):
    rules.model_exists('Subsession')
    rules.model_exists('Group')
    rules.model_exists('Player')

    config = rules.config
    Player = config.get_model('Player')
    Group = config.get_model('Group')
    Subsession = config.get_model('Subsession')

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
                        rules.push_warning(
                            '{} has attribute "{}", which is not a model field, '
                            'and will therefore not be saved '
                            'to the database.'.format(
                                Model.__name__, attr
                            ),
                            hint='Consider changing to "{} = models.{}(...)"'.format(attr, model_field_substitutes[_type])
                        )
                    # if people just need an iterable of choices for a model field,
                    # they should use a tuple, not list or dict
                    if _type in {list, dict, set}:
                        warning = (
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

                        rules.push_warning(warning)


@register_rules(id='otree.E003')
def constants(rules, **kwargs):
    cond = (
        rules.module_exists('models') and
        rules.class_exists('models', 'Constants')
    )
    if cond:
        Constants = rules.get_module_attr('models', 'Constants')
        attrs = ['name_in_url', 'players_per_group', 'num_rounds']
        for attr_name in attrs:
            if not hasattr(Constants, attr_name):
                msg = "models.py: 'Constants' class needs to define '{}'"
                rules.push_error(msg.format(attr_name))
        ppg = Constants.players_per_group
        if ppg == 0 or ppg == 1:
            rules.push_error(
                "models.py: 'Constants.players_per_group' cannot be {}. You "
                "should set it to None, which makes the group "
                "all players in the subsession.".format(ppg)
            )


@register_rules(id='otree.E004')
def pages_function(rules, **kwargs):
    if rules.module_exists('views'):
        views_module = rules.get_module('views')
        try:
            page_list = views_module.page_sequence
        except:
            rules.push_error('views.py is missing the variable page_sequence.')
            return
        else:
            for i, ViewCls in enumerate(page_list):
                # there is no good reason to include Page in page_sequence.
                # however, WaitPage could belong there. it works fine currently
                # and can save the effort of subclassing
                if ViewCls.__name__ == 'Page':
                    msg = (
                        "views.py: page_sequence cannot contain "
                        "a class called 'Page'. You should subclass Page "
                        "and give your page a different name."
                    )
                    rules.push_error(msg)
                if issubclass(ViewCls,
                              otree.views.abstract.WaitPage):
                    if hasattr(ViewCls, 'before_next_page'):
                        rules.push_error(
                            'views.py: "{}" defines before_next_page, '
                            'which is not valid on wait pages.'.format(
                                ViewCls.__name__)
                        )
                    if ViewCls.group_by_arrival_time:
                        if i > 0:
                            rules.push_error(
                                'views.py: "{}" has group_by_arrival_time=True, so '
                                'it must be placed first in page_sequence.'.format(
                                    ViewCls.__name__))
                        if ViewCls.wait_for_all_groups:
                            rules.push_error(
                                'views.py: "{}" has group_by_arrival_time=True, so '
                                'it cannot have wait_for_all_groups=True also.'.format(
                                    ViewCls.__name__))

                elif issubclass(ViewCls,
                                otree.views.abstract.Page):
                    # ok
                    pass
                else:
                    msg = 'views.py: "{}" is not a valid page'.format(ViewCls)
                    rules.push_error(msg)


@register_rules(id='otree.E005')
def templates_have_no_dead_code(rules, **kwargs):
    for template_name in rules.get_template_names():
        rules.template_has_no_dead_code(template_name)


@register_rules(id='otree.E006', once_per_project=True)
def unique_sessions_names(rules, **kwargs):
    already_seen = set()
    for st in settings.SESSION_CONFIGS:
        st_name = st["name"]
        if st_name in already_seen:
            msg = "Duplicate SESSION_CONFIG name '{}'".format(st_name)
            rules.push_error(msg)
        else:
            already_seen.add(st_name)


@register_rules(id='otree.E009', once_per_project=True)
def unique_room_names(rules, **kwargs):
    already_seen = set()
    for room in getattr(settings, 'ROOMS', []):
        room_name = room["name"]
        if room_name in already_seen:
            msg = "Duplicate ROOM name '{}'".format(room_name)
            rules.push_error(msg)
        else:
            already_seen.add(room_name)


@register_rules(id='otree.E007')
def template_encoding(rules, **kwargs):
    for template_name in rules.get_template_names():
        rules.template_has_valid_encoding(template_name)


@register_rules(id='otree.E008')
def templates_have_valid_syntax(rules, **kwargs):
    for template_name in rules.get_template_names():
        rules.template_has_valid_syntax(template_name)


# TODO: startapp should pass validation checks
