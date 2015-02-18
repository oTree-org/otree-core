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

@register.simple_tag(takes_context=True)
def mturk_submit_button(context):
    participant = context['player'].participant
    assignment_id = participant.mturk_assignment_id
    url = "https://www.mturk.com/mturk/externalSubmit"
    url = add_params_to_url(url, {'assignmentId': assignment_id,
                                  'foo': 'bar'})
    return mark_safe('<a href="%s">Continue</a>' % url)

@register.simple_tag(takes_context=True)
def mturk_start_button(context):
    if context['hit_accepted'] == True:
        url = reverse('mturk_start', args=(context['session'].code))
        url = add_params_to_url(url, {'assignment_id': context['assignment_id'],
                                      'worker_id': context['worker_id']})
        return mark_safe('<a href="%s">Continue</a>' % url)
    else:
        return 'Please accept the hit'

@register.simple_tag
def active_page(request, view_name):
    if not request:
        return ""
    try:
        url_name = resolve(request.path_info).url_name
        return "active" if url_name == view_name else ""
    except Resolver404:
        return ""
