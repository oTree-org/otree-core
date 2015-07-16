from collections import namedtuple
import sys

from django.db import models
from django.template import Node
from django.template import TemplateSyntaxError
from django.template import Variable
from django.template import VariableDoesNotExist
from django.template.base import token_kwargs
from django.template.loader import get_template
from django.utils import six

import floppyforms.templatetags.floppyforms as floppyforms_templatetags


FORM_UNRENDERED_FIELDS = 'form_unrendered_fields'


UnrenderedField = namedtuple('UnrenderedField', ('name', 'html_name', 'field'))


def mark_field_as_rendered(context, bound_field):
    if not hasattr(context, '_rendered_fields'):
        context._rendered_fields = set()
    context._rendered_fields.add(bound_field.field)


class FormNode(floppyforms_templatetags.FormNode):
    def get_form_instance(self, context):
        extra_context = self.get_extra_context(context)
        form = extra_context[self.single_template_var]
        return form

    def get_rendered_fields(self, context):
        return getattr(context, '_rendered_fields', [])

    def render(self, context):
        result = super(FormNode, self).render(context)
        form = self.get_form_instance(context)
        if form is not None:
            missing_fields = context.get(FORM_UNRENDERED_FIELDS, [])
            for field_name, field in form.fields.items():
                if field not in self.get_rendered_fields(context):
                    missing_fields.append(UnrenderedField(
                        field_name, form.add_prefix(field_name), field))
            context[FORM_UNRENDERED_FIELDS] = missing_fields
        return result


class MarkFieldAsRenderedNode(Node):
    def __init__(self, tagname, field_variable):
        self.tagname = tagname
        self.field_variable = field_variable

    def mark_field_as_rendered(self, context, bound_field):
        mark_field_as_rendered(context, bound_field)

    def render(self, context):
        bound_field = self.field_variable.resolve(context)
        self.mark_field_as_rendered(context, bound_field)
        return ''

    @classmethod
    def parse(cls, parser, token):
        bits = token.split_contents()
        tagname = bits.pop(0)
        if len(bits) != 1:
            raise TemplateSyntaxError(
                '{tagname!r} takes exactly one argument.'.format(
                    tagname=tagname))
        field_variable = Variable(bits.pop(0))
        return cls(tagname, field_variable)


class FormFieldNode(Node):
    default_template = get_template('otree/tags/_formfield.html')

    def __init__(self, field_variable_name, with_arguments):
        self.field_variable_name = field_variable_name
        self.with_arguments = with_arguments

    def get_form_instance(self, context):
        try:
            return Variable('form').resolve(context)
        except VariableDoesNotExist as exception:
            msg = (
                "The 'formfield' templatetag expects a 'form' variable "
                "in the context.")
            six.reraise(
                type(exception),
                type(exception)(msg + ' ' + str(exception)),
                sys.exc_info()[2])

    def resolve_bound_field(self, context):
        bound_field = Variable(self.field_variable_name).resolve(context)
        return bound_field

    def get_bound_field(self, context):
        # First we try to resolve the {% formfield player.name %} syntax were
        # player is a model instance.
        if '.' in self.field_variable_name:
            form = self.get_form_instance(context)
            model_instance_name, field_name = \
                self.field_variable_name.split('.', -1)
            model_instance = Variable(model_instance_name).resolve(context)
            if isinstance(model_instance, models.Model):
                if form.instance != model_instance:
                    raise ValueError(
                        "Variable '{model_instance_name}' "
                        "({model_instance!r}) is different to the "
                        "model instance set in the form "
                        "({form_model_instance!r}).".format(
                            model_instance_name=model_instance_name,
                            model_instance=model_instance,
                            form_model_instance=form.instance))
                try:
                    return form[field_name]
                except KeyError:
                    raise ValueError(
                        "Field '{field_name}' was referenced in the template, "
                        "but was not included in the Page's 'form_fields' "
                        "in views.py ".format(
                            field_name=field_name))

        # Second we try to resolve it to a bound field.
        # No field found, so we return None.
        bound_field = Variable(self.field_variable_name).resolve(context)

        # We assume it's a BoundField when 'as_widget', 'as_hidden' and
        # 'errors' attribtues are available.
        if (
                not hasattr(bound_field, 'as_widget') or
                not hasattr(bound_field, 'as_hidden') or
                not hasattr(bound_field, 'errors')):
            raise ValueError(
                "The given variable '{variable_name}' ({variable!r}) is "
                "neither a model field nor a form field.".format(
                    variable_name=self.field_variable_name,
                    variable=bound_field))
        return bound_field

    def get_extra_context(self, context):
        bound_field = self.get_bound_field(context)
        extra_context = {
            'bound_field': bound_field
        }
        if self.with_arguments:
            with_context = dict(
                (name, var.resolve(context))
                for name, var in self.with_arguments.items())
            # If the with argument label="" was set explicitly, we set it to
            # None. That is required to differentiate between 'use the default
            # label since we didn't set any in the template' and 'do not print
            # a label at all' as defined in
            # https://github.com/oTree-org/otree-core/issues/325
            if with_context.get('label', None) == '':
                with_context['label'] = None
            extra_context.update(with_context)
        return extra_context

    def render(self, context):
        extra_context = self.get_extra_context(context)
        context.update(extra_context)
        try:
            rendered = self.default_template.render(context)
        finally:
            context.pop()
        mark_field_as_rendered(context, extra_context['bound_field'])
        return rendered

    @classmethod
    def parse(cls, parser, token):
        bits = token.split_contents()
        tagname = bits.pop(0)
        if len(bits) < 1:
            raise TemplateSyntaxError(
                "{tagname!r} requires at least one argument.".format(
                    tagname=tagname))
        field = bits.pop(0)
        if bits:
            with_ = bits.pop(0)
            if with_ != 'with':
                raise TemplateSyntaxError(
                    "{tagname}'s second argument must be 'with'.".format(
                        tagname=tagname))
            with_arguments = token_kwargs(bits, parser, support_legacy=False)
            if not with_arguments:
                raise TemplateSyntaxError(
                    "'with' in {tagname} tag needs at least one keyword "
                    "argument.".format(tagname=tagname))
        else:
            with_arguments = {}
        if bits:
            raise TemplateSyntaxError(
                'Unkown argument for {tagname} tag: {bits!r}'.format(
                    tagname=tagname,
                    bits=bits))
        return cls(field, with_arguments)


def defaultlabel(given_label, default):
    # We check for an explicit None here in order to allow the label to be made
    # empty.
    if given_label is None:
        return None
    if not given_label:
        return default
    return given_label
