from __future__ import division, absolute_import
from . import models
from otree.api import Page
from .models import Constants

class Page1(Page):
    template_name = 'bots_check_html/PageWithNoFields.html'
    timeout_seconds = 10

class Page2(Page):
    template_name = 'bots_check_html/PageWithNoFields.html'

    form_model = models.Player
    form_fields = ['field_not_in_template']


page_sequence = [
    Page1,
    Page2
]
