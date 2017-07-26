from otree.api import (
    models, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, widgets
)


doc = """
Test misc functionality of a 1-player game
"""


class Constants(BaseConstants):
    name_in_url = 'form_validation'
    players_per_group = None
    num_rounds = 1


class Subsession(BaseSubsession):
    pass

class Group(BaseGroup):

    # example field
    min_max = models.CurrencyField(
        doc="""
        Description of this field, for documentation
        """,
        min=1,
        max=1
    )

    min_max_dynamic = models.CurrencyField()


class Player(BasePlayer):

    blank = models.CharField(blank=True)

    add100_1 = models.PositiveIntegerField()
    add100_2 = models.PositiveIntegerField()

    even_int = models.PositiveIntegerField()

    dynamic_choices = models.CharField()

    blank_dynamic_choices = models.IntegerField(blank=True)

    choices_flat = models.CurrencyField(
        widget=widgets.RadioSelect(),
        choices=[c(1), c(2)]
    )

    choices = models.IntegerField(
        widget=widgets.RadioSelect(),
        choices=[[1, 'A'], [2, 'B']]
    )

    dynamic_radio = models.CharField(widget=widgets.RadioSelectHorizontal())

    min_max_dynamic = models.CurrencyField()
    min_max_blank = models.FloatField(blank=True, min=1, max=1)
    min_max_blank2 = models.FloatField(blank=True, min=1, max=1)

    equals_one = models.IntegerField(initial=1)