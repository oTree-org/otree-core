from decimal import Decimal
from markupsafe import escape, Markup
from wtforms.compat import text_type
from wtforms.widgets import html_params
from otree import settings
from otree.currency import CURRENCY_SYMBOLS
from gettext import gettext

# the below code is adapted from wtforms


class BaseWidget:
    has_value = True

    def __call__(self, field, **render_kw):

        self.field = field
        self.render_kw = render_kw
        render_kw.setdefault('id', field.id)
        if self.has_value and 'value' not in render_kw:
            render_kw['value'] = field._value()
        if 'required' not in render_kw and 'required' in getattr(field, 'flags', []):
            render_kw['required'] = True
        return Markup(''.join(self.get_html_fragments()))

    def get_html_fragments(self):
        raise NotImplementedError

    def attrs(self):
        return html_params(name=self.field.name, **self.render_kw)


class NumberWidget(BaseWidget):
    def __init__(self, step):
        self.step = step

    def get_html_fragments(self):
        yield f'<input type="number" class="form-control" step="{self.step}" %s>' % self.attrs()


class CurrencyWidget(BaseWidget):
    def __init__(self):
        if settings.USE_POINTS:
            if getattr(settings, 'POINTS_CUSTOM_NAME', None):
                CURRENCY_SYMBOL = settings.POINTS_CUSTOM_NAME
                places = settings.POINTS_DECIMAL_PLACES
            else:
                # Translators: the label next to a "points" input field
                CURRENCY_SYMBOL = gettext('points')
                places = settings.REAL_WORLD_CURRENCY_DECIMAL_PLACES
        else:
            CURRENCY_SYMBOL = CURRENCY_SYMBOLS.get(
                settings.REAL_WORLD_CURRENCY_CODE, settings.REAL_WORLD_CURRENCY_CODE
            )
            places = settings.REAL_WORLD_CURRENCY_DECIMAL_PLACES
        self.symbol = CURRENCY_SYMBOL
        self.step = str(10 ** -places)

    def get_html_fragments(self):
        yield '''<div class="input-group input-group-narrow">'''
        yield f'<input type="number" class="form-control" step="{self.step}" {self.attrs()}>'
        yield f'''
            <div class="input-group-append">
                <span class="input-group-text">{self.symbol}</span>
            </div>
        </div> 
        '''


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


class Dropdown(BaseWidget):
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


class DropdownOption(object):
    """
    Renders the individual option from a select field.

    This is just a convenience for various custom rendering situations, and an
    option by itself does not constitute an entire field.
    """

    def __call__(self, field, **kwargs):
        return Dropdown.render_option(
            field._value(), field.label.text, field.checked, **kwargs
        )


class RadioSelect(BaseWidget):
    has_value = False

    def get_html_fragments(self):
        yield '<div %s>' % html_params(**self.render_kw)
        for subfield in self.field:
            yield '<div class="form-check">%s %s</div>' % (subfield(), subfield.label)
        yield '</div>'


class RadioSelectHorizontal(BaseWidget):
    has_value = False

    def get_html_fragments(self):
        for subfield in self.field:
            yield f'''
            <div class="form-check form-check-inline">
                {subfield()}
                <label for="{subfield.id}" class="form-check-label">{subfield.label.text}</label>
            </div>
            '''


class RadioOption(BaseWidget):
    def __call__(self, field, **kwargs):
        if field.checked:
            kwargs['checked'] = True
        return super().__call__(field, **kwargs)

    def get_html_fragments(self):
        yield '<input class="form-check-input" type="radio" %s>' % self.attrs()
