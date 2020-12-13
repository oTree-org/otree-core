import re
from gettext import gettext
from otree.chat import chat_template_tag
from .loader import ibis_loader
from ibis.nodes import register, Node, Expression
from ibis import Template
from ibis.errors import (
    TemplateSyntaxError,
    TemplateRenderingError,
    TemplateError,
    UndefinedVariable,
)
import wtforms.fields as wtfields
from otree.common import CSRF_TOKEN_NAME


def parse_as_kwarg(arg, expected_name, token) -> Expression:
    prefix = expected_name + '='
    if not arg.startswith(prefix):
        msg = f'Expected argument {prefix}, but got: {arg}'
        raise ValueError(msg)
    return Expression(arg[len(prefix) :], token)


@register('formfield')
class FormFieldNode(Node):
    def process_token(self, token):
        args = smart_split(token.text)[1:]
        assert len(args) in [
            1,
            2,
        ], f"formfield tag takes 1 or 2 arguments, not {len(args)}"
        arg0 = args[0]
        # compat with old format
        if arg0.startswith('player.') or arg0.startswith('group.'):
            arg0 = "'{}'".format(arg0.split('.')[1])
        self.field_expr = Expression(arg0, token)
        if len(args) == 2:
            assert args[1].startswith('label=')
            self.label_expr = Expression(args[1][len('label=') :], token)
        else:
            self.label_expr = None

    def wrender(self, context):
        fname = self.field_expr.eval(context)
        if not isinstance(fname, str):
            raise TypeError(
                "formfield argument should be a string, e.g. {% formfield 'contribution' %}"
            )
        if fname not in context['form']:
            raise ValueError(f'Field not found in form: {fname:.20}')
        fld: wtfields.Field = context['form'][fname]
        label_expr = self.label_expr
        if label_expr:
            label = label_expr.eval(context)
        else:
            label = fld.label
        # if not label.endswith(':'):
        #    label += ':'
        classes = 'mb-3 _formfield'

        if fld.errors:
            classes += ' has-errors'
        return Template(
            '''
<div class="{{classes}}">
    <label class="col-form-label" for="id_{{fname}}">{{label}}</label>
    <div class="controls">
        {{fld}}
    </div>
    {% if fld.description %}
        <small>
            <p class="form-text text-muted">{{ fld.description }}</p>
        </small>
    {% endif %}
    {% if errors %}
        <div class="form-control-errors">
            {% for error in errors %}{{ error }}<br/>{% endfor %}
        </div>
    {% endif %}
</div>'''
        ).render(
            dict(fld=fld, fname=fname, label=label, classes=classes, errors=fld.errors),
            strict_mode=True,
        )


@register('formfields')
class FormFields(Node):
    def wrender(self, context):
        form = context['form']
        field_names = [f.name for f in form]
        return Template(
            '''{% for name in field_names %}{% formfield name %}{% endfor %}'''
        ).render(field_names=field_names, form=form, strict_mode=True)


@register('load')
class LoadShim(Node):
    def wrender(self, context):
        return ''


@register('comment', 'endcomment')
class BlockComment(Node):
    def wrender(self, context):
        return ''


@register('ibis_tag_lvar')
class OpenVar(Node):
    def wrender(self, context):
        return '{{'


@register('ibis_tag_rvar')
class CloseVar(Node):
    def wrender(self, context):
        return '}}'


@register('ibis_tag_lblock')
class OpenBlock(Node):
    def wrender(self, context):
        return '{%'


@register('ibis_tag_rblock')
class CloseBlock(Node):
    def wrender(self, context):
        return '%}'


NEXT_BTN_TEXT = gettext('Next')


@register('next_button')
class NextButton(Node):
    def wrender(self, context):
        return f'''
        <p>
            <button class="otree-btn-next btn btn-primary">{NEXT_BTN_TEXT}</button>
        </p>
        '''


@register('csrf_token')
class CsrfToken(Node):
    def wrender(self, context):
        return context[CSRF_TOKEN_NAME]


@register('chat')
class ChatNode(Node):
    channel_expr = None
    nickname_expr = None

    def process_token(self, token):
        args = token.text.split()[1:]
        assert len(args) <= 2, '{% chat %} tag takes at most 2 arguments'
        for arg in args:
            if arg.startswith('channel='):
                self.channel_expr = parse_as_kwarg(arg, 'channel', token)
            if arg.startswith('nickname='):
                self.nickname_expr = parse_as_kwarg(arg, 'nickname', token)

    def wrender(self, context):
        kwargs = {}
        if self.channel_expr:
            kwargs['channel'] = self.channel_expr.eval(context)
        if self.nickname_expr:
            kwargs['nickname'] = self.nickname_expr.eval(context)
        tag_context = chat_template_tag(context, **kwargs)
        return ibis_loader('otree/tags/chat.html').render(tag_context, strict_mode=True)


class BackslashError(ValueError):
    pass


@register('static')
class StaticNode(Node):
    def process_token(self, token):
        args = token.text.split()[1:]
        assert len(args) == 1, '{% static %} tag takes 1 argument'
        [path] = args
        if '\\' in path:
            msg = (
                r'{{% static {} %}} '
                r'contains a backslash ("\"); '
                r'you should change it to a forward slash ("/").'
            ).format(path)
            raise BackslashError(msg)

        self.path_expr = Expression(path, token)

    def wrender(self, context):
        from otree.asgi import app

        return app.router.url_path_for('static', path=self.path_expr.eval(context))


@register('url')
class UrlNode(Node):
    def process_token(self, token):
        args = token.text.split()[1:]
        assert len(args) >= 1, '{% url %} tag takes at least 1 argument'
        self.name_expr = Expression(args[0], token)
        self.arg_exprs = [Expression(arg, token) for arg in args[1:]]

    def wrender(self, context):
        """like url_for, but allows us to pass url params positionally"""
        from otree.asgi import app

        values = [arg.eval(context) for arg in self.arg_exprs]
        url_name = self.name_expr.eval(context)
        for route in app.router.routes:
            if route.name == url_name:
                arg_names = list(route.param_convertors.keys())
                path_params = dict(zip(arg_names, values))
                return route.url_path_for(route.name, **path_params)
        raise Exception(f'no match for url "{url_name}"')


# Expression to match some_token and some_token="with spaces" (and similarly
# for single-quoted strings).
_smart_split_re = re.compile(
    r"""
    ((?:
        [^\s'"]*
        (?:
            (?:"(?:[^"\\]|\\.)*" | '(?:[^'\\]|\\.)*')
            [^\s'"]*
        )+
    ) | \S+)
""",
    re.VERBOSE,
)


def smart_split(text):
    """from django"""
    ret = []
    for bit in _smart_split_re.finditer(str(text)):
        ret.append(bit.group(0))
    return ret
