import ast
import collections
import logging
import operator
import re
import types

import wtforms.fields as wtfields
from otree.chat import chat_template_tag
from otree.common import CSRF_TOKEN_NAME, FULL_DECIMAL_PLACES
from otree.common2 import url_of_static
from otree.i18n import format_number
from gettext import gettext
from otree.forms.fields import CheckboxField

from . import errors
from . import filters
from . import ibis_loader
from . import utils

logger = logging.getLogger(__name__)

# Dictionary of registered keywords for instruction tags.
instruction_keywords = {}


# List of registered endwords for instruction tags with block scope.
instruction_endwords = []


# Decorator function for registering handler classes for instruction tags.
# Registering an endword gives the instruction tag block scope.
def register(keyword, endword=None):
    def register_node_class(node_class):
        instruction_keywords[keyword] = (node_class, endword)
        if endword:
            instruction_endwords.append(endword)
        return node_class

    return register_node_class


# Helper class for evaluating expression strings.
#
# An Expression object is initialized with an expression string parsed from a template. An
# expression string can contain a variable name or a Python literal, optionally followed by a
# sequence of filters.
#
# The Expression object handles the rather convoluted process of parsing the string, evaluating
# the literal or resolving the variable, calling the variable if it resolves to a callable, and
# applying the filters to the resulting object. The consumer simply needs to call the expression's
# .eval() method and supply an appropriate Context object.
#
# Examples of valid expression syntax include:
#
#     foo.bar.baz|default('bam')|escape
#     'foo', 'bar', 'baz'|random
#
# Arguments can be passed to callables using bracket syntax:
#
#     foo.bar.baz('bam')|filter(25, 'text')
#
class Expression:

    re_func_call = re.compile(r'^([\w.]+)\((.*)\)$')
    re_varstring = re.compile(r'^[\w.]+$')

    def __init__(self, expr, token):
        self.token = token
        self.filters = []
        pipe_split = utils.splitc(expr.strip(), '|', strip=True)
        self._parse_primary_expr(pipe_split[0])
        self._parse_filters(pipe_split[1:])
        if self.is_literal:
            self.literal = self._apply_filters_to_literal(self.literal)

    def _parse_primary_expr(self, expr):
        try:
            self.literal = ast.literal_eval(expr)
            self.is_literal = True
        except:
            self.is_literal = False
            (
                self.is_func_call,
                self.varstring,
                self.func_args,
            ) = self._try_parse_as_func_call(expr)
            if not self.is_func_call and not self.re_varstring.match(expr):
                msg = f"Unparsable expression '{expr}'"
                raise errors.TemplateSyntaxError(msg, self.token)

    def _try_parse_as_func_call(self, expr):
        match = self.re_func_call.match(expr)
        if not match:
            return False, expr, []
        func_name = match.group(1)
        func_args = utils.splitc(match.group(2), ',', True, True)
        for index, arg in enumerate(func_args):
            try:
                func_args[index] = ast.literal_eval(arg)
            except Exception as err:
                msg = f"Unparsable argument '{arg}'. "
                msg += f"Arguments must be valid Python literals."
                raise errors.TemplateSyntaxError(msg, self.token) from err
        return True, func_name, func_args

    def _parse_filters(self, filter_list):
        for filter_expr in filter_list:
            _, filter_name, filter_args = self._try_parse_as_func_call(filter_expr)
            if filter_name in filters.filtermap:
                self.filters.append(
                    (filter_name, filters.filtermap[filter_name], filter_args)
                )
            else:
                msg = f"Unrecognised filter name '{filter_name}'"
                raise errors.TemplateSyntaxError(msg, self.token)

    def _apply_filters_to_literal(self, obj):
        for name, func, args in self.filters:
            try:
                obj = func(obj, *args)
            except Exception as err:
                msg = f"Error applying filter '{name}' to literal."
                raise errors.TemplateSyntaxError(msg, self.token) from err
        return obj

    def eval(self, context):
        if self.is_literal:
            return self.literal
        else:
            return self._resolve_variable(context)

    def _resolve_variable(self, context):
        obj = context.resolve(self.varstring, self.token)
        if self.is_func_call or isinstance(
            obj, (types.MethodType, types.BuiltinMethodType)
        ):
            try:
                obj = obj(*self.func_args)
            except Exception as err:
                msg = f"Error calling function '{self.varstring}' "
                msg += f"in template '{self.token.template_id}', line {self.token.line_number}."
                raise errors.TemplateRenderingError(msg, self.token) from err
        return self._apply_filters_to_variable(obj)

    def _apply_filters_to_variable(self, obj):
        for name, func, args in self.filters:
            try:
                obj = func(obj, *args)
            except Exception as err:
                msg = f"Error applying filter '{name}' to variable"
                raise errors.TemplateRenderingError(msg, self.token) from err
        return obj


# Base class for all node objects. To render a node into a string call its .render() method.
# Subclasses shouldn't override the base .render() method; instead they should override
# .wrender() which ensures that any uncaught exceptions are wrapped in a TemplateRenderingError.
class Node:
    def __init__(self, token=None, children=None):
        self.token = token
        self.children = children or []
        try:
            self.process_token(token)
        except errors.TemplateError:
            raise
        except Exception as err:
            if token:
                tagname = (
                    f"'{token.keyword}'" if token.type == "INSTRUCTION" else token.type
                )
                msg = f"Error while parsing the {tagname} tag "
                msg += f"{err.__class__.__name__}: {err}"
            else:
                msg = f"Syntax error: {err.__class__.__name__}: {err}"
            raise errors.TemplateSyntaxError(msg, token) from err

    def __str__(self):
        return self.to_str()

    def to_str(self, depth=0):
        output = ["·  " * depth + f"{self.__class__.__name__}"]
        for child in self.children:
            output.append(child.to_str(depth + 1))
        return "\n".join(output)

    def render(self, context):
        try:
            return self.wrender(context)
        except errors.TemplateError:
            raise
        except Exception as err:
            if self.token:
                tagname = (
                    f"'{self.token.keyword}'"
                    if self.token.type == "INSTRUCTION"
                    else self.token.type
                )
                msg = f"Error while rendering the {tagname} tag: "
                msg += f"{err.__class__.__name__}: {err}"
            else:
                msg = f"Unexpected rendering error: {err.__class__.__name__}: {err}"
            raise errors.TemplateRenderingError(msg, self.token) from err

    def wrender(self, context):
        return ''.join(child.render(context) for child in self.children)

    def process_token(self, token):
        pass

    def exit_scope(self):
        pass

    def split_children(self, delimiter_class):
        for index, child in enumerate(self.children):
            if isinstance(child, delimiter_class):
                return self.children[:index], child, self.children[index + 1 :]
        return self.children, None, []


# TextNodes represent ordinary template text, i.e. text not enclosed in tag delimiters.
class TextNode(Node):
    def wrender(self, context):
        return self.token.text


# A PrintNode evaluates an expression and prints its result. Multiple expressions can be listed
# separated by 'or' or '||'. The first expression to resolve to a truthy value will be printed.
# (If none of the expressions are truthy the final value will be printed regardless.)
#
#     {{ <expr> or <expr> or <expr> }}
#
# Alternatively, print statements can use the ternary operator: ?? ::
#
#     {{ <test-expr> ?? <expr1> :: <expr2> }}
#
# If <test-expr> is truthy, <expr1> will be printed, otherwise <expr2> will be printed.
#
# Note that *either* 'or'-chaining or the ternary operator can be used in a single print statement,
# but not both.
class PrintNode(Node):
    def process_token(self, token):

        # Check for a ternary operator.
        chunks = utils.splitre(token.text, (r'\?\?', r'\:\:'), True)
        if len(chunks) == 5 and chunks[1] == '??' and chunks[3] == '::':
            self.is_ternary = True
            self.test_expr = Expression(chunks[0], token)
            self.true_branch_expr = Expression(chunks[2], token)
            self.false_branch_expr = Expression(chunks[4], token)

        # Look for a list of 'or' separated expressions.
        else:
            self.is_ternary = False
            exprs = utils.splitre(token.text, (r'\s+or\s+', r'\|\|'))
            self.exprs = [Expression(e, token) for e in exprs]

    def wrender(self, context):
        if self.is_ternary:
            if self.test_expr.eval(context):
                content = self.true_branch_expr.eval(context)
            else:
                content = self.false_branch_expr.eval(context)
        else:
            for expr in self.exprs:
                content = expr.eval(context)
                if content:
                    break

        return localize(content)


# ForNodes implement `for ... in ...` looping over iterables.
#
#     {% for <var> in <expr> %} ... [ {% empty %} ... ] {% endfor %}
#
# ForNodes support unpacking into multiple loop variables:
#
#     {% for <var1>, <var2> in <expr> %}
#
@register('for', 'endfor')
class ForNode(Node):

    regex = re.compile(r'for\s+(\w+(?:,\s*\w+)*)\s+in\s+(.+)')

    def process_token(self, token):
        match = self.regex.match(token.text)
        if match is None:
            msg = f"Malformed tag"
            raise errors.TemplateSyntaxError(msg, token)
        self.loopvars = [var.strip() for var in match.group(1).split(',')]
        self.expr = Expression(match.group(2), token)

    def wrender(self, context):
        collection = self.expr.eval(context)
        if collection:
            collection = list(collection)
            length = len(collection)
            unpack = len(self.loopvars) > 1
            output = []
            for index, item in enumerate(collection):
                context.push()
                if unpack:
                    try:
                        unpacked = dict(zip(self.loopvars, item))
                    except Exception as err:
                        msg = f"Unpacking error"
                        raise errors.TemplateRenderingError(msg, self.token) from err
                    else:
                        context.update(unpacked)
                else:
                    context[self.loopvars[0]] = item
                # oTree modified this to be more similar to django
                context['forloop'] = {
                    'counter0': index,
                    'counter': index + 1,
                }
                output.append(self.for_branch.render(context))
                context.pop()
            return ''.join(output)
        else:
            return self.empty_branch.render(context)

    def exit_scope(self):
        for_nodes, _, empty_nodes = self.split_children(EmptyNode)
        self.for_branch = Node(None, for_nodes)
        self.empty_branch = Node(None, empty_nodes)


# Delimiter node to implement for/empty branching.
@register('empty')
class EmptyNode(Node):
    pass


# IfNodes implement if/elif/else branching.
#
#     {% if [not] <expr> %} ... {% endif %}
#     {% if [not] <expr> <operator> <expr> %} ... {% endif %}
#     {% if <...> %} ... {% elif <...> %} ... {% else %} ... {% endif %}
#
# IfNodes support 'and' and 'or' conjunctions; 'and' has higher precedence so:
#
#     if a and b or c and d
#
# is treated as:
#
#     if (a and b) or (c and d)
#
# Note that explicit brackets are not supported.
@register('if', 'endif')
class IfNode(Node):

    condition = collections.namedtuple('Condition', 'negated lhs op rhs')

    re_condition = re.compile(
        r'''
        (not\s+)?(.+?)\s+(==|!=|<|>|<=|>=|not[ ]in|in)\s+(.+)
        |
        (not\s+)?(.+)
        ''',
        re.VERBOSE,
    )

    operators = {
        '==': operator.eq,
        '!=': operator.ne,
        '<': operator.lt,
        '>': operator.gt,
        '<=': operator.le,
        '>=': operator.ge,
        'in': lambda a, b: a in b,
        'not in': lambda a, b: a not in b,
    }

    def process_token(self, token):
        self.tag = token.keyword
        try:
            conditions = token.text.split(None, 1)[1]
        except:
            msg = f"Malformed tag"
            raise errors.TemplateSyntaxError(msg, token) from None

        self.condition_groups = [
            [
                self.parse_condition(condstr)
                for condstr in utils.splitre(or_block, (r'\s+and\s+', r'&&'))
            ]
            for or_block in utils.splitre(conditions, (r'\s+or\s+', r'\|\|'))
        ]

    def parse_condition(self, condstr):
        match = self.re_condition.match(condstr)
        if match.group(2):
            return self.condition(
                negated=bool(match.group(1)),
                lhs=Expression(match.group(2), self.token),
                op=self.operators[match.group(3)],
                rhs=Expression(match.group(4), self.token),
            )
        else:
            return self.condition(
                negated=bool(match.group(5)),
                lhs=Expression(match.group(6), self.token),
                op=None,
                rhs=None,
            )

    def eval_condition(self, cond, context):
        try:
            if cond.op:
                result = cond.op(cond.lhs.eval(context), cond.rhs.eval(context))
            else:
                result = operator.truth(cond.lhs.eval(context))
        except Exception as err:
            logger.exception(str(err))  # temp workaround for starlette issue
            msg = f"Error evaluating the condition in the "
            msg += f"'{self.tag}' tag"
            raise errors.TemplateRenderingError(msg, self.token) from err
        if cond.negated:
            result = not result
        return result

    def wrender(self, context):
        for condition_group in self.condition_groups:
            for condition in condition_group:
                is_true = self.eval_condition(condition, context)
                if not is_true:
                    break
            if is_true:
                break
        if is_true:
            return self.true_branch.render(context)
        else:
            return self.false_branch.render(context)

    def exit_scope(self):
        if_nodes, elif_node, elif_nodes = self.split_children(ElifNode)
        if elif_node:
            self.true_branch = Node(None, if_nodes)
            self.false_branch = IfNode(elif_node.token, elif_nodes)
            self.false_branch.exit_scope()
            return
        if_nodes, _, else_nodes = self.split_children(ElseNode)
        self.true_branch = Node(None, if_nodes)
        self.false_branch = Node(None, else_nodes)


# Delimiter node to implement if/elif branching.
@register('elif')
class ElifNode(Node):
    pass


# Delimiter node to implement if/else branching.
@register('else')
class ElseNode(Node):
    pass


# IncludeNodes include a sub-template.
#
#     {% include <expr> %}
#
# Requires a template name which can be supplied as either a string literal or a variable
# resolving to a string. This name will be passed to the registered template loader.
@register('include')
class IncludeNode(Node):
    def process_token(self, token):
        self.variables = {}
        parts = utils.splitre(token.text[7:], ["with"])
        if len(parts) == 1:
            self.template_arg = parts[0]
            self.template_expr = Expression(parts[0], token)
        elif len(parts) == 2:
            self.template_arg = parts[0]
            self.template_expr = Expression(parts[0], token)
            chunks = utils.splitc(parts[1], "&", strip=True, discard_empty=True)
            for chunk in chunks:
                try:
                    name, expr = chunk.split('=', 1)
                    self.variables[name.strip()] = Expression(expr.strip(), token)
                except:
                    raise errors.TemplateSyntaxError(
                        "Malformed 'include' tag.", token
                    ) from None
        else:
            raise errors.TemplateSyntaxError("Malformed 'include' tag.", token)

    def wrender(self, context):
        template_name = self.template_expr.eval(context)
        if isinstance(template_name, str):
            template = ibis_loader.load(template_name)
            context.push()
            for name, expr in self.variables.items():
                context[name] = expr.eval(context)
            rendered = template.root_node.render(context)
            context.pop()
            return rendered
        else:
            msg = f"Invalid argument for the 'include' tag. "
            msg += f"The variable '{self.template_arg}' should evaluate to a string. "
            msg += f"This variable has the value: {repr(template_name)}."
            raise errors.TemplateRenderingError(msg, self.token)


# ExtendNodes implement template inheritance. They indicate that the current template inherits
# from or 'extends' the specified parent template.
#
#     {% extends "parent.txt" %}
#
# Requires a template name to pass to the registered template loader. This must be supplied as a
# string literal (not a variable) as the parent template must be loaded at compile-time.
@register('extends')
class ExtendsNode(Node):
    def process_token(self, token):
        try:
            tag, arg = token.text.split(None, 1)
        except:
            msg = f"Malformed tag"
            raise errors.TemplateSyntaxError(msg, token) from None
        expr = Expression(arg, token)

        if expr.is_literal and isinstance(expr.literal, str):
            template = ibis_loader.load(expr.literal)
            self.children.append(template.root_node)
        else:
            msg = (
                f"Malformed 'extends' tag. The template name must be a string literal."
            )
            raise errors.TemplateSyntaxError(msg, token)


# BlockNodes implement template inheritance.
#
#    {% block title %} ... {% endblock %}
#
# A block tag defines a titled block of content that can be overridden by similarly titled blocks
# in child templates.
@register('block', 'endblock')
class BlockNode(Node):
    def process_token(self, token):
        self.title = token.text[5:].strip()

    def wrender(self, context):
        # We only want to render the first block of any given title that we encounter
        # in the node tree, although we want to substitute the content of the last
        # block of that title in its place.
        block_list = context.template.block_registry[self.title]
        if block_list[0] is self:
            return self.render_block(context, block_list[:])
        else:
            return ''

    def render_block(self, context, block_list):
        # A call to {{ super }} inside a block renders and returns the content of the
        # block's immediate ancestor. That ancestor may itself contain a {{ super }}
        # call, so we start at the end of the list and recursively work our way
        # backwards, popping off nodes as we go.
        if block_list:
            last_block = block_list.pop()
            context.push()
            context['super'] = lambda: self.render_block(context, block_list)
            output = ''.join(child.render(context) for child in last_block.children)
            context.pop()
            return output
        else:
            return ''


# Caches a complex expression under a simpler alias.
#
#    {% with <alias> = <expr> %} ... {% endwith %}
#
@register('with', 'endwith')
class WithNode(Node):
    def process_token(self, token):
        try:
            alias, expr = token.text[4:].split('=', 1)
        except:
            msg = f"Malformed tag"
            raise errors.TemplateSyntaxError(msg, token) from None
        self.alias = alias.strip()
        self.expr = Expression(expr.strip(), token)

    def wrender(self, context):
        context.push()
        context[self.alias] = self.expr.eval(context)
        rendered = ''.join(child.render(context) for child in self.children)
        context.pop()
        return rendered


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
        if len(args) == 0:
            msg = 'formfield tag requires the name of the field'
            raise errors.TemplateSyntaxError(msg, token)
        if len(args) > 2:
            msg = (
                f"formfield tag takes 1 or 2 arguments, not {len(args)}. "
                "Delete the keyword 'with' or make sure there are no spaces around the ="
            )
            raise errors.TemplateSyntaxError(msg, token)
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
        from .template import Template

        arg0 = self.field_expr.eval(context)
        fld: wtfields.Field
        if isinstance(arg0, str):
            if arg0 not in context['form']:
                raise ValueError(f'Field not found in form: {arg0:.20}')
            fld = context['form'][arg0]
        elif isinstance(arg0, wtfields.Field):
            fld = arg0
        else:
            raise TypeError(
                "formfield argument should be a string, e.g. {% formfield 'contribution' %}"
            )

        label_expr = self.label_expr
        if label_expr:
            label = label_expr.eval(context)
        else:
            label = fld.label.text
        # if not label.endswith(':'):
        #    label += ':'

        is_checkbox = isinstance(fld, CheckboxField)

        if is_checkbox:
            classes = 'form-check'
        else:
            classes = 'mb-3 _formfield'

        if fld.errors:
            classes += ' has-errors'

        return Template(
            '''
<div class="{{classes}}">
    {% if is_checkbox %}
      {{fld}}
      <label class="form-check-label" for="{{fld.id}}">
        {{label}}
      </label>
    {% else %}
        <label class="col-form-label" for="{{fld.id}}">{{label}}</label>
        <div class="controls">
            {{fld}}
        </div>
    {% endif %}
    {% if fld.description %}
        <p>
        <small>
            <p class="form-text text-muted">{{ fld.description }}</p>
        </small>
        </p>
    {% endif %}
    {% if errors %}
        <div class="form-control-errors">
            {% for error in errors %}{{ error }}<br/>{% endfor %}
        </div>
    {% endif %}
</div>'''
        ).render(
            dict(
                fld=fld,
                label=label,
                classes=classes,
                errors=fld.errors,
                is_checkbox=is_checkbox,
            ),
            strict_mode=True,
        )


@register('formfield_errors')
class FieldErrorsNode(Node):
    def process_token(self, token):
        try:
            tag, arg = token.text.split()
        except:
            msg = f"1 argument required"
            raise errors.TemplateSyntaxError(msg, token) from None
        self.field_expr = Expression(arg, token)

    def wrender(self, context):
        fieldname = self.field_expr.eval(context)

        if not isinstance(fieldname, str):
            raise TypeError("argument must be a string")
        if fieldname not in context['form']:
            raise ValueError(f'Field not found in form: {fieldname:.20}')

        fld: wtfields.Field = context['form'][fieldname]
        if not fld.errors:
            return ''
        # if the user wants custom styling, they can loop over form.xyz.errors
        return '<div class="form-control-errors">' + '<br/>'.join(fld.errors) + '</div>'


@register('formfields')
class FormFields(Node):
    def wrender(self, context):
        from .template import Template

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
    """
    It's better to use {# #} style comments because with a block like this,
    because that prevents parsing of its contents,
    whereas this style comment means children will get parsed,
    meaning that any incorrectly used tags will cause
    a TemplateSyntaxError. 
    """

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


@register('next_button')
class NextButton(Node):
    def wrender(self, context):
        NEXT_BTN_TEXT = gettext('Next')
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
        assert len(args) <= 2, '{{ chat }} tag takes at most 2 arguments'
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
        return ibis_loader.load('otree/tags/chat.html').render(
            tag_context, strict_mode=True
        )


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
        path = self.path_expr.eval(context)
        return url_of_static(path)


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


def localize(v):
    if isinstance(v, float):
        return format_number(v, places=FULL_DECIMAL_PLACES)
    return str(v)


@register('blocktrans', 'endblocktrans')
class BlockTransNode(Node):
    """just a shim"""

    pass


@register('trans')
class TransNode(Node):
    """this is only for the user's own translations, because it uses gettext with the 'messages.mo' domain"""

    def process_token(self, token):
        args = smart_split(token.text)[1:]
        assert len(args) == 1, f"trans tag takes 1 argument, not {len(args)}"
        self.term_literal = Expression(args[0], token)

    def wrender(self, context):
        return gettext(self.term_literal.eval(context))
