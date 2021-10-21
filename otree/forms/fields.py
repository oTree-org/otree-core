import decimal
import wtforms.fields as wtfields
from otree.currency import Currency, to_dec
from otree.i18n import format_number, core_gettext
from otree import common

from . import widgets as wg


def handle_localized_number_input(val):
    if val is None:
        return val
    return val.replace(',', '.')


class FloatField(wtfields.FloatField):
    widget = wg.FloatWidget()

    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = float(handle_localized_number_input(valuelist[0]))
            except ValueError:
                self.data = None
                # hack: hide this from pybabel, which seems to scan for all
                # functions that end with 'gettext('.
                # wtforms already contains these translations, so they should
                # not end up in our .po file.
                _gt = self.gettext
                raise ValueError(_gt('Not a valid float value'))

    def _value(self):
        if self.data is None:
            return ''
        return format_number(self.data, places=common.FULL_DECIMAL_PLACES)


class CurrencyField(wtfields.Field):
    widget = wg.CurrencyWidget()

    def process_formdata(self, valuelist):
        if valuelist and valuelist[0]:
            try:
                data = Currency(handle_localized_number_input(valuelist[0]))
            except (decimal.InvalidOperation, ValueError):
                self.data = None
                # see the note above about gettext
                _gt = self.gettext
                raise ValueError(_gt('Not a valid decimal value'))
        else:
            data = None
        self.data = data

    def _value(self):
        if self.data is None:
            return ''
        return format_number(to_dec(self.data), places=common.FULL_DECIMAL_PLACES)


class StringField(wtfields.StringField):
    widget = wg.TextInput()


class IntegerField(wtfields.IntegerField):
    widget = wg.IntegerWidget()


def _selectfield_getitem(self, index):
    if not isinstance(index, int):
        raise IndexError
    for (i, choice) in enumerate(self):
        if index == i:
            return choice
    raise IndexError


def __iter__(self):
    """
    Add 'required' attribute to HTML:
    https://github.com/wtforms/wtforms/pull/615/files
    """
    opts = dict(
        widget=self.option_widget,
        _name=self.name,
        _form=None,
        _meta=self.meta,
        validators=self.validators,
    )
    for i, (value, label, checked) in enumerate(self.iter_choices()):
        opt = self._Option(label=label, id='%s-%d' % (self.id, i), **opts)
        opt.process(None, value)
        opt.checked = checked
        yield opt


class RadioField(wtfields.RadioField):
    widget = wg.RadioSelect()
    option_widget = wg.RadioOption()
    __getitem__ = _selectfield_getitem
    __iter__ = __iter__


class RadioFieldHorizontal(wtfields.RadioField):
    widget = wg.RadioSelectHorizontal()
    option_widget = wg.RadioOption()
    __getitem__ = _selectfield_getitem
    __iter__ = __iter__


class DropdownField(wtfields.SelectField):
    widget = wg.Select()
    option_widget = wg.SelectOption()
    __getitem__ = _selectfield_getitem
    __iter__ = __iter__


class TextAreaField(StringField):
    """
    This field represents an HTML ``<textarea>`` and can be used to take
    multi-line input.
    """

    widget = wg.TextArea()


class CheckboxField(wtfields.BooleanField):
    widget = wg.CheckboxInput()
