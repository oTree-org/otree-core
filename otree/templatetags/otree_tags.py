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

from django import template
from django.template.loader import render_to_string
from django.core.urlresolvers import Resolver404, reverse

from .otree_forms import FormNode
from .otree_forms import FormFieldNode
from .otree_forms import MarkFieldAsRenderedNode
from .otree_forms import defaultlabel
from otree.common import Currency


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
            return render_to_string('otree/tags/NextButton.html', context)
        finally:
            context.pop()

    @classmethod
    def parse(cls, parser, tokens):
        return cls()


register.tag('next_button', NextButtonNode.parse)


def c(val):
    return Currency(val)


register.filter('c', c)


@register.simple_tag
def active_page(request, view_name, *args, **kwargs):
    if not request:
        return ""
    try:
        url = reverse(view_name, args=args)
        return "active" if url == request.path_info else ""
    except Resolver404:
        return ""


@register.simple_tag
def add_class(var, css_class, *extra_css_classes):
    '''
    tag for specifying css classes
    '''
    try:
        if var or extra_css_classes:
            css_class_template = 'class="%s"'
        else:
            return ''
        css_classes = list(extra_css_classes)
        if var:
            css_classes.append(css_class)
        return css_class_template % ' '.join(css_classes)
    except Resolver404:
        return ""


register.tag('pageform', FormNode.parse)
register.tag('mark_field_as_rendered', MarkFieldAsRenderedNode.parse)
register.tag('formfield', FormFieldNode.parse)
register.filter('defaultlabel', defaultlabel)
