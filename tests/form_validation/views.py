from . import models
from tests.utils import BlankTemplatePage
from otree.api import Currency as c

import sys, inspect


class Page(BlankTemplatePage):
    '''Most pages have just 1 field, so optimize for that but allow overriding'''

    form_model = models.Player
    yields = []

    def get_form_fields(self):
        return [self.field]

    @classmethod
    def get_yields(cls):
        # return a list of post dicts. only the last one should succeed
        return [{cls.field: x} for x in cls.yields]


class ChoicesFlat(Page):
    field = 'choices_flat'
    yields = [c(0), c(1)]


class Choices(Page):
    field = 'choices'
    yields = [0, 1]


class ErrorMessage(Page):
    def get_form_fields(self):
        return ['add100_1', 'add100_2']

    def error_message(self, values):
        if values['add100_1'] + values['add100_2'] != 100:
            return 'The numbers must add up to 100'

    @classmethod
    def get_yields(cls):
        return [
            {'add100_1': 1, 'add100_2': 98},
            {'add100_1': 1, 'add100_2': 99}
        ]


class FieldErrorMessage(Page):
    field = 'even_int'
    yields = [1, 2]

    def even_int_error_message(self, value):
        if value % 2:
            return 'Must be an even number'


class DynamicChoices(Page):
    field = 'dynamic_choices'
    yields = ['c', 'a']

    def dynamic_choices_choices(self):
        return [
            ['a', 'first choice'],
            ['b', 'second choice'],
        ]


class BlankDynamicChoices(Page):
    field = 'blank_dynamic_choices'

    @classmethod
    def get_yields(cls):
        return [{}]

    def blank_dynamic_choices_choices(self):
        return [1, 2]


class MinMax(Page):
    # test it on group also
    form_model = models.Group
    field = 'min_max'
    yields = [0, 2, 1]


class MinMaxDynamic(Page):
    field = 'min_max_dynamic'
    yields = [0, 2, 1]

    def min_max_dynamic_min(self):
        return 1

    def min_max_dynamic_max(self):
        # test referencing the instance
        return self.player.equals_one


class MinMaxBlank(Page):
    field = 'min_max_blank'

    @classmethod
    def get_yields(cls):
        # should succeed without any input
        return [{}]


class MinMaxBlank2(Page):
    field = 'min_max_blank2'
    yields = [2, 1]


def is_page_subclass(PageClass):
    return (
        inspect.isclass(PageClass)
        and issubclass(PageClass, Page)
        and PageClass != Page
    )


inspect_result = inspect.getmembers(sys.modules[__name__], is_page_subclass)

# getmembers returns  all the members of an object
# in a list of (name, value) pairs sorted by name.

page_sequence = [e[1] for e in inspect_result]
