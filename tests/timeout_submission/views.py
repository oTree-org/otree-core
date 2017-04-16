# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from otree.api import WaitPage
from tests.utils import BlankTemplatePage as Page
from .models import Constants


class Page1(Page):
    form_model = models.Player
    form_fields = ['f_currency', 'f_bool', 'f_posint', 'f_char', 'f_float']

    timeout_seconds = 5

    def error_message(self, values):
        if values['f_char'] == Constants.invalid_f_char:
            return 'error!'

    def before_next_page(self):
        if self.timeout_happened:
            self.player.timeout_happened = True


page_sequence = [
    Page1,
]
