from typing import Dict

from django.db import models
from django.template import Node
from django.template import TemplateSyntaxError
from django.template import Variable, Context
from django.template.base import Token, FilterExpression
from django.template.base import token_kwargs

from otree.models_concrete import UndefinedFormModel


class FormFieldNode(Node):
    template_name = 'otree/tags/_formfield.html'

    @classmethod
    def parse(cls, parser, token: Token):

        # here is how split_contents() works:

        # {% formfield player.f1 label="f1 label" %}
        # ...yields:
        # ['formfield', 'player.f1', 'label="f1 label"']

        # {% formfield player.f2 "f2 label with no kwarg" %}
        # ...yields:
        # ['formfield', 'player.f2', '"f2 label with no kwarg"']

        # handle where the user did {% formfield player.f label = "foo" %}
        token.contents = token.contents.replace('label = ', 'label=')
        bits = token.split_contents()
        tagname = bits.pop(0)
        if len(bits) < 1:
            msg = f"{tagname} requires the name of the field."
            raise TemplateSyntaxError(msg)
        field_name = bits.pop(0)
        if bits[:1] == ['with']:
            bits.pop(0)
        arg_dict = token_kwargs(bits, parser, support_legacy=False)
        if bits:
            msg = f'Unused parameter to formfield tag: {bits[0]}'
            raise TemplateSyntaxError(msg)
        return cls(field_name, **arg_dict)

    def __init__(self, first_arg, label: FilterExpression = None):
        self.first_arg = first_arg
        self.label_arg = label

    def get_form_instance(self, context):
        return Variable('form').resolve(context)

    def resolve_bound_field(self, context):
        bound_field = Variable(self.first_arg).resolve(context)
        return bound_field

    def get_bound_field(self, context):
        first_arg = self.first_arg
        form = self.get_form_instance(context)

        field_name = None
        # {% formfield player.contribution %}
        if first_arg.startswith('player.') or first_arg.startswith('group.'):
            field_name = first_arg.split('.')[1]
        # eventually we may encourage this format:
        # {% formfield "contribution" %}
        # this allows easier looping over form fields,
        # and will let us delete most of this template tag and just use inclusion_tag.
        elif first_arg[0] in ('"', "'") and first_arg[0] == first_arg[-1]:
            field_name = first_arg[1:-1]
        else:
            # Second we try to resolve it to a bound field.
            # we need this so people can do:
            # {% for field in form %}{% formfield field %}{% endfor %}
            variable = Variable(first_arg).resolve(context)
            if isinstance(variable, str):
                field_name = variable
            elif (
                hasattr(variable, 'as_widget')
                and hasattr(variable, 'as_hidden')
                and hasattr(variable, 'errors')
            ):
                # We assume it's a BoundField
                return variable
        if field_name:
            # oTree internally uses {% formfield %} with non-modelforms,
            # but that's always like {% formfield form.foo %}, never {% formfield "foo" %}
            if type(form.instance) == UndefinedFormModel:
                msg = (
                    'Template contains a formfield, but '
                    'you did not set form_model on the Page class.'
                )
                raise ValueError(msg)
            try:
                return form[field_name]
            except KeyError:
                msg = (
                    f"'{field_name}' was used as a formfield in the template, "
                    "but was not included in the Page's 'form_fields'"
                )
                raise ValueError(msg) from None
        msg = f'Invalid argument to formfield tag: {first_arg}'
        raise ValueError(msg)

    def get_tag_specific_context(self, context: Context) -> Dict:
        bound_field = self.get_bound_field(context)
        if self.label_arg:
            label = self.label_arg.resolve(context)
            # If the with argument label="" was set explicitly, we set it to
            # None. That is required to differentiate between 'use the default
            # label since we didn't set any in the template' and 'do not print
            # a label at all' as defined in
            # https://github.com/oTree-org/otree-core/issues/325
        else:
            label = bound_field.label
        return dict(
            bound_field=bound_field, help_text=bound_field.help_text, label=label,
        )

    def render(self, context: Context):
        t = context.template.engine.get_template(self.template_name)
        tag_specific_context = self.get_tag_specific_context(context)
        new_context = context.new(tag_specific_context)
        return t.render(new_context)
