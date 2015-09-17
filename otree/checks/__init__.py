import os
import glob
import types
from importlib import import_module
from functools import wraps
import inspect

from django.apps import apps
from django.conf import settings
from django.core.checks import register, Error
from django.template import Template
from django.template import TemplateSyntaxError

import otree.views.abstract


class Rules(object):
    """A helper class incapsulating common checks.

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

    common_buffer = {}

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
            for filename in filter(lambda f: f.endswith('.html'), files):
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
            with open(template_name, 'r') as f:
                Template(f.read())
        except (IOError, OSError):
            pass
        except TemplateSyntaxError as error:
            template_source, position = error.django_template_source
            snippet = format_source_snippet(
                template_source.source,
                arrow_position=position[0])
            return self.error(
                'Template syntax error in {template}\n'
                '\n'
                '{snippet}\n'
                '\n'
                'Error: {error}'.format(
                    template=template_name,
                    error=error,
                    snippet=snippet))

    @rule
    def template_has_no_dead_code(self, template_name):
        from otree.checks.templates import get_unreachable_content
        from otree.checks.templates import has_valid_encoding

        # Only test files that are valid templates.
        if not has_valid_encoding(template_name):
            return

        try:
            with open(template_name, 'r') as f:
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


def _get_all_configs():
    return [
        app
        for app in apps.get_app_configs()
        if app.name in settings.INSTALLED_OTREE_APPS]


def register_rules(tags=(), id=None):
    """Transform a function based on rules, to a something
    django.core.checks.register takes. Automatically loops over all games.
    Passes Rules instance as first argument.

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

    cond = (
        rules.dir_exists('templates') and
        rules.dir_exists('templates/' + rules.config.label)
    )
    if cond:
        # check for files in templates, but not in templates/<label>
        misplaced_templates = set(glob.glob(
            os.path.join(rules.get_path('templates'), '*.html')
        ))
        misplaced_templates.discard(rules.config.label)
        if misplaced_templates:
            hint = 'Move template files to "templates/%s"' % rules.config.label
            rules.push_error(
                "Templates files in root template directory",
                hint=hint, id='otree.E001'
            )


@register_rules(id='otree.E002')
def model_classes(rules, **kwargs):
    rules.model_exists('Subsession')
    rules.model_exists('Group')
    rules.model_exists('Player')


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
        if getattr(Constants, 'players_per_group', None) == 1:
            rules.push_error(
                "models.py: 'Constants.players_per_group' cannot be 1. You "
                "should set it to None, which makes the group "
                "all players in the subsession."
            )


@register_rules(id='otree.E004')
def pages_function(rules, **kwargs):
    if rules.module_exists('views'):
        views_module = rules.get_module('views')
        try:
            page_list = views_module.page_sequence
        except:
            rules.push_error('views.py: need a list page_sequence '
                             'that contains a list of pages')
            return
        else:
            for ViewCls in page_list:
                cond = not issubclass(
                    ViewCls, otree.views.abstract.FormPageOrWaitPageMixin
                )
                if cond:
                    msg = 'views.py: "{}" is not a valid page'.format(ViewCls)
                    rules.push_error(msg)


@register_rules(id='otree.E005')
def templates_have_no_dead_code(rules, **kwargs):
    for template_name in rules.get_template_names():
        rules.template_has_no_dead_code(template_name)


@register_rules(id='otree.E006')
def unique_sessions_names(rules, **kwargs):
    if "unique_session_names_already_run" not in rules.common_buffer:
        rules.common_buffer["unique_session_names_already_run"] = True
        buff = set()
        for st in settings.SESSION_CONFIGS:
            st_name = st["name"]
            if st_name in buff:
                msg = "Duplicate SESSION_CONFIG name '{}'".format(st_name)
                rules.push_error(msg)
            else:
                buff.add(st_name)


@register_rules(id='otree.E007')
def template_encoding(rules, **kwargs):
    for template_name in rules.get_template_names():
        rules.template_has_valid_encoding(template_name)


@register_rules(id='otree.E008')
def templates_have_valid_syntax(rules, **kwargs):
    for template_name in rules.get_template_names():
        rules.template_has_valid_syntax(template_name)


# TODO: startapp should pass validation checks
