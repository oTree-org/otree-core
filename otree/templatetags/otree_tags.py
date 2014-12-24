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
