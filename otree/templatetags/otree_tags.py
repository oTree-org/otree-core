#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# DOCS
# =============================================================================

"""Template tags to for the otree template users.

"""


# =============================================================================
# IMPORTS
# =============================================================================

from .otree_forms import FormNode
from .otree_forms import FormFieldNode
from .otree_forms import MarkFieldAsRenderedNode
from django import template
from django.template.loader import render_to_string
from django.core.urlresolvers import resolve, Resolver404, reverse
from django.utils.safestring import mark_safe
from otree.common import Currency
from otree.common_internal import add_params_to_url


# =============================================================================
# CONSTANTS
# =============================================================================

register = template.Library()


# =============================================================================
# TAGS
# =============================================================================

class NextButtonNode(template.Node):
    def render(self, context):
        context.update({})
        try:
            return render_to_string('otree/NextButton.html', context)
        finally:
            context.pop()

    @classmethod
    def parse(cls, parser, tokens):
        return cls()


register.tag('next_button', NextButtonNode.parse)


def c(val):
    return Currency(val)


register.filter('c', c)

#FIXME: deprecated, remove this
@register.simple_tag(takes_context=True)
def mturk_submit_button(context):
    pass

@register.simple_tag
def active_page(request, view_name):
    if not request:
        return ""
    try:
        url_name = resolve(request.path_info).url_name
        return "active" if url_name == view_name else ""
    except Resolver404:
        return ""


register.tag('pageform', FormNode.parse)
register.tag('mark_field_as_rendered', MarkFieldAsRenderedNode.parse)
register.tag('formfield', FormFieldNode.parse)
