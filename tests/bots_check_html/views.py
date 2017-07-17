from __future__ import division, absolute_import
from . import models
from otree.api import Page
from .models import Constants


class HtmlMissingFields(Page):
    def is_displayed(self):
        return self.player.id_in_group == 1

    template_name = 'bots_check_html/NoFields.html'

    form_model = models.Player
    form_fields = ['field_not_in_template']


class HtmlMissingButton(Page):
    def is_displayed(self):
        return self.player.id_in_group == 2

    template_name = 'bots_check_html/NoButton.html'


class TimeoutPage(Page):
    def is_displayed(self):
        return self.player.id_in_group == 3

    template_name = 'bots_check_html/NoFields.html'
    timeout_seconds = 10


page_sequence = [
    HtmlMissingFields,
    HtmlMissingButton,
    TimeoutPage,

]
