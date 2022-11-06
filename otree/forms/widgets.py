from decimal import Decimal
from markupsafe import escape, Markup
from wtforms.compat import text_type
from wtforms.widgets import html_params
from otree import settings
from otree.currency import CURRENCY_SYMBOLS
from otree.i18n import core_gettext


# the below code is adapted from wtforms


class BaseWidget:
    has_value = True

    def __call__(self, field, **render_kw):

        self.field = field
        render_kw.setdefault('id', field.id)
        if self.has_value and 'value' not in render_kw:
            render_kw['value'] = field._value()
        if 'required' not in render_kw and 'required' in getattr(field, 'flags', []):
            render_kw['required'] = True
        self.render_kw = render_kw
        return Markup(''.join(self.get_html_fragments()))

    def get_html_fragments(self):
        raise NotImplementedError

    def attrs(self):
        return html_params(name=self.field.name, **self.render_kw)


class CheckboxInput(BaseWidget):
    def __call__(self, field, **render_kw):
        if getattr(field, 'checked', field.data):
            render_kw['checked'] = True
        return super().__call__(field, **render_kw)

    def get_html_fragments(self):
        yield ('<input type="checkbox" class="form-check-input" %s>' % (self.attrs()))


class IntegerWidget(BaseWidget):
    """
    better to use number input when we can, because:
    - on mobile it pops up the number keypad
    - better validation of numbers
    """

    def get_html_fragments(self):
        min = self.render_kw.get('min')
        if min is not None and min >= 0:
            inputmode = 'numeric'
        else:
            inputmode = ''

        yield f'<input type="number" class="form-control" inputmode="{inputmode}" %s>' % self.attrs()


class FloatWidget(BaseWidget):
    """
    use input type='text' instead of 'number' because:
    - it allows comma as decimal separator
    - no annoying spinner widget
    - no problems dealing with step= argument.
    """

    def get_html_fragments(self):
        min = self.render_kw.get('min')
        if min is not None and min >= 0:
            inputmode = 'decimal'
        else:
            inputmode = ''
        yield f'<input type="text" class="form-control" inputmode="{inputmode}" %s>' % self.attrs()


class CurrencyWidget(BaseWidget):
    def __init__(self):
        if settings.USE_POINTS:
            if getattr(settings, 'POINTS_CUSTOM_NAME', None):
                CURRENCY_SYMBOL = settings.POINTS_CUSTOM_NAME
            else:
                # Translators: the label next to a "points" input field
                CURRENCY_SYMBOL = core_gettext('points')
            places = settings.POINTS_DECIMAL_PLACES
        else:
            CURRENCY_SYMBOL = CURRENCY_SYMBOLS.get(
                settings.REAL_WORLD_CURRENCY_CODE, settings.REAL_WORLD_CURRENCY_CODE
            )
            places = settings.REAL_WORLD_CURRENCY_DECIMAL_PLACES
        self.symbol = CURRENCY_SYMBOL
        self.places = places

    def get_html_fragments(self):
        yield '''<div class="input-group input-group-narrow">'''

        min = self.render_kw.get('min')
        if min is None or min < 0:
            inputmode = ''
        elif self.places == 0:
            inputmode = 'numeric'
        else:
            inputmode = 'decimal'

        if self.places == 0:
            yield f'<input type="number" class="form-control" inputmode="{inputmode}" {self.attrs()}>'
        else:
            yield f'<input type="text" class="form-control" inputmode="{inputmode}" {self.attrs()}>'
        yield f'''<span class="input-group-text">{self.symbol}</span>'''
        yield '</div>'


class TextInput(BaseWidget):
    def get_html_fragments(self):
        yield '<input type="text" class="form-control" %s>' % self.attrs()


class TextArea(BaseWidget):
    """
    Renders a multi-line text area.

    `rows` and `cols` ought to be passed as keyword args when rendering.
    """

    def get_html_fragments(self):
        yield (
            '<textarea class="form-control" %s>\r\n%s</textarea>'
            % (self.attrs(), escape(self.field._value()))
        )


class Select(BaseWidget):
    """
    Renders a select field.

    The field must provide an `iter_choices()` method which the widget will
    call on rendering; this method must yield tuples of
    `(value, label, selected)`.
    """

    has_value = False

    def get_html_fragments(self):
        yield '<select class="form-select" %s>' % self.attrs()
        yield '<option value="">--------</option>'
        for val, label, selected in self.field.iter_choices():
            yield self.render_option(val, label, selected)
        yield '</select>'

    @classmethod
    def render_option(cls, value, label, selected, **kwargs):
        if value is True:
            # Handle the special case of a 'True' value.
            value = text_type(value)
        options = dict(kwargs, value=value)
        if selected:
            options['selected'] = True
        return Markup(
            '<option %s>%s</option>' % (html_params(**options), escape(label))
        )


class SelectOption(object):
    """
    Renders the individual option from a select field.

    This is just a convenience for various custom rendering situations, and an
    option by itself does not constitute an entire field.
    """

    def __call__(self, field, **kwargs):
        return Select.render_option(
            field._value(), field.label.text, field.checked, **kwargs
        )


class RadioSelect(BaseWidget):
    has_value = False

    def get_html_fragments(self):

        yield '<div %s>' % html_params(**self.render_kw)
        for subfield in self.field:
            # 'required' attribute is missing in wtforms
            # https://github.com/wtforms/wtforms/pull/615
            # let's wait until that change gets released,
            # before fixing the case of {{ for option in field }}...
            # which unfortunately skips past this workaround
            subfield_html = (
                subfield(required=True)
                if self.render_kw.get('required')
                else subfield()
            )
            yield '<div class="form-check">%s %s</div>' % (
                subfield_html,
                subfield.label,
            )
        yield '</div>'


class RadioSelectHorizontal(BaseWidget):
    has_value = False

    def get_html_fragments(self):
        for subfield in self.field:
            subfield_html = (
                subfield(required=True)
                if self.render_kw.get('required')
                else subfield()
            )
            yield f'''
            <div class="form-check form-check-inline">
                {subfield_html}
                <label for="{subfield.id}" class="form-check-label">{subfield.label.text}</label>
            </div>
            '''


class RadioOption(BaseWidget):
    def __call__(self, field, **kwargs):
        if field.checked:
            kwargs['checked'] = True
        # see comment above about missing required attribute.
        return super().__call__(field, **kwargs)

    def get_html_fragments(self):
        yield '<input class="form-check-input" type="radio" %s>' % self.attrs()
