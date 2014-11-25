import os
import types
from importlib import import_module
from functools import wraps

from django.apps import apps
from django.conf import settings
from django.core.checks import register, Error


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
    def __init__(self, config, errors):
        self.config = config
        self.errors = errors

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
        kwargs.setdefault('obj', self.config.name)
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
            return self.error(
                'No "%s" file found in game folder' % filename,
                id='otree.E001',
            )

    @rule
    def dir_exists(self, filename):
        if not os.path.isdir(self.get_path(filename)):
            return self.error(
                'No "%s" directory found in game folder' % filename,
                id='otree.E001',
            )

    @rule
    def model_exists(self, name):
        try:
            self.config.get_model(name)
        except LookupError:
            return self.error(
                'Model "%s" not found' % name,
                id='otree.E002',
            )

    @rule
    def module_exists(self, module):
        try:
            module = self.get_module(module)
        except ImportError as e:
            return self.error(
                'Can\'t import module "%s": %s' % (module, e),
                id='otree.E003',
            )

    @rule
    def class_exists(self, module, name):
        module = self.get_module(module)
        if not hasattr(module, name) or isinstance(getattr(module, name), type):
            return self.error(
                'No class "%s" in module "%s"' % (name, module.__name__),
                id='otree.E004',
            )


def _get_all_configs():
    return [apps.app_configs[label] for label in settings.INSTALLED_OTREE_APPS]


def register_rules(*tags):
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
                rules = Rules(config, errors)
                func(rules, **kwargs)
            return errors
        return wrapper
    return decorator


# Checks

@register_rules()
def files(rules, **kwargs):
    rules.file_exists('models.py')
    rules.file_exists('views.py')
    rules.file_exists('tests.py')

    if rules.dir_exists('templates') and rules.dir_exists('templates/' + rules.config.name):
        # check for files in templates, but not in templates/<name>
        misplaced_templates = set(os.listdir(rules.get_path('templates')))
        misplaced_templates.discard(rules.config.name)
        if misplaced_templates:
            rules.push_error(
                "Templates files in root template directory",
                hint='Move template files to "templates/%s"' % rules.config.name,
                id='otree.E001'
            )


@register_rules()
def model_classes(rules, **kwargs):
    rules.model_exists('Subsession')
    rules.model_exists('Group')
    rules.model_exists('Player')


@register_rules()
def constants(rules, **kwargs):
    if rules.module_exists('models') and rules.class_exists('models', 'Constants'):
        Constants = rules.get_module_attr('models', 'Constants')
        # TODO: check constant attributes, their types, etc.
