import otree.common_internal
from django import template
from django.core.urlresolvers import Resolver404, reverse
from django.template.loader import render_to_string
from otree.chat.models import (
    chat_template_tag)
from otree.common import safe_json
from otree.currency import Currency
from .otree_forms import FormFieldNode
from .otree_forms import defaultlabel


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


def active_page(request, view_name, *args, **kwargs):
    if not request:
        return ""
    try:
        url = reverse(view_name, args=args)
        return "active" if url == request.path_info else ""
    except Resolver404:
        return ""


NO_USER_MSG = '''
You must set ADMIN_USERNAME and
ADMIN_PASSWORD in settings.py
(or disable authentication by unsetting AUTH_LEVEL).
'''


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

def c(val):
    return Currency(val)

def my_abs(val):
    '''
    it seems you can't use a builtin as a filter_func:
    File "C:\oTree\venv\lib\site-packages\django\template\base.py", line 1179, in filter
    filter_func._filter_name = name
    AttributeError: 'builtin_function_or_method' object has no attribute '_filter_name'
    '''
    return abs(val)

register = template.Library()
register.tag('formfield', FormFieldNode.parse)
register.tag('next_button', NextButtonNode.parse)
register.simple_tag(name='ensure_superuser_exists',
                    func=ensure_superuser_exists)
register.simple_tag(name='active_page', func=active_page)
register.filter(name='c', filter_func=c)
register.filter(name='abs', filter_func=my_abs)
register.filter('json', safe_json)
register.filter('defaultlabel', defaultlabel)

# this code is duplicated in otree.py
@register.inclusion_tag('otreechat_core/widget.html', takes_context=True)
def chat(context, *args, **kwargs):
    return chat_template_tag(context, *args, **kwargs)