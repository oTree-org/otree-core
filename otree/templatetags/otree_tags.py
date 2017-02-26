from django import template
from django.template.loader import render_to_string
from django.core.urlresolvers import Resolver404, reverse
from .otree_forms import FormFieldNode
from .otree_forms import defaultlabel
from otree.common import Currency, safe_json
import otree.common_internal


register = template.Library()


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


NO_USER_MSG = '''
You must set ADMIN_USERNAME and
ADMIN_PASSWORD in settings.py
(or disable authentication by unsetting AUTH_LEVEL).
'''


@register.simple_tag
def ensure_superuser_exists():
    '''
    Creates a superuser on the fly, so that the user doesn't have to migrate
    or resetdb to get a superuser.
    If eventually we use migrations instead of resetdb, then maybe won't
    need this anymore.
    '''
    success = otree.common_internal.ensure_superuser_exists()
    if success:
        return ''
    return NO_USER_MSG


register.tag('formfield', FormFieldNode.parse)


# =============================================================================
# FILTERS
# =============================================================================


@register.filter
def c(val):
    return Currency(val)


@register.filter(name="abs")
def abs_value(var):
    return abs(var)


register.filter('json', safe_json)
register.filter('defaultlabel', defaultlabel)
