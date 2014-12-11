import os
import types
from importlib import import_module
from functools import wraps

from django.apps import apps
from django.conf import settings
from django.core.checks import register, Error

import otree.views.abstract


class Rules(object):
    """
    A helper class incapsulating common checks.

    Usage:
        rules = Rules(app_configs, errors_list)

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
    def __init__(self, config, errors, id=None):
        self.config = config
        self.errors = errors
        self.id = id

    def rule(meth):
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

    # Helper meythods

    def get_path(self, name):
        return os.path.join(self.config.path, name)

    def get_module(self, name):
        return import_module(self.config.name + '.' + name)

    def get_module_attr(self, module, name):
        if not isinstance(module, types.ModuleType):
            module = self.get_module(module)
        return getattr(module, name)

    # Rule methods

    @rule
    def file_exists(self, filename):
        if not os.path.isfile(self.get_path(filename)):
            return self.error('No "%s" file found in game folder' % filename)

    @rule
    def dir_exists(self, filename):
        if not os.path.isdir(self.get_path(filename)):
            return self.error('No "%s" directory found in game folder' % filename)

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
        if not hasattr(module, name) or isinstance(getattr(module, name), type):
            return self.error('No class "%s" in module "%s"' % (name, module.__name__))


def _get_all_configs():
    return [
        app
        for app in apps.get_app_configs()
        if app.name in settings.INSTALLED_OTREE_APPS]


def register_rules(tags=(), id=None):
    """
    Transform a function based on rules, to a something django.core.checks.register takes.
    Automatically loops over all games. Passes Rules instance as first argument.
    """
    def decorator(func):
        @register(*tags)
        @wraps(func)
        def wrapper(app_configs, **kwargs):
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
    rules.file_exists('tests.py')

    if rules.dir_exists('templates') and rules.dir_exists('templates/' + rules.config.label):
        # check for files in templates, but not in templates/<label>
        misplaced_templates = set(os.listdir(rules.get_path('templates')))
        misplaced_templates.discard(rules.config.label)
        if misplaced_templates:
            rules.push_error(
                "Templates files in root template directory",
                hint='Move template files to "templates/%s"' % rules.config.label,
                id='otree.E001'
            )


@register_rules(id='otree.E002')
def model_classes(rules, **kwargs):
    rules.model_exists('Subsession')
    rules.model_exists('Group')
    rules.model_exists('Player')


@register_rules(id='otree.E003')
def constants(rules, **kwargs):
    if rules.module_exists('models') and rules.class_exists('models', 'Constants'):
        Constants = rules.get_module_attr('models', 'Constants')
        for attr_name in ['name_in_url', 'players_per_group', 'number_of_rounds']:
            if not hasattr(Constants, attr_name):
                rules.push_error(
                    "models.py: 'Constants' class needs to define '{}'".format(attr_name),
                )


@register_rules(id='otree.E004')
def pages_function(rules, **kwargs):
    if rules.module_exists('views'):
        views_module = rules.get_module('views')
        try:
            page_list = views_module.pages()
        except:
            rules.push_error('views.py: need a function pages() that returns a list of pages')
            return
        else:
            for ViewCls in page_list:
                if not issubclass(ViewCls, otree.views.abstract.FormPageOrWaitPageMixin):
                    rules.push_error('views.py: "{}" is not a valid page'.format(ViewCls))
                if issubclass(ViewCls, otree.views.Page) and not getattr(ViewCls, 'template_name'):
                    rules.push_error(
                        'views.py: Page class "{}" is missing a template_name attribute'.format(ViewCls)
                    )


@register_rules(id='otree.E005')
def templates(rules, **kwargs):
    path = rules.get_path('templates')
    print path


# TODO: startapp should pass validation checks
