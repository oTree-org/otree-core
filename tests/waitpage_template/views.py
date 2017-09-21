# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from otree.api import WaitPage, Page
from .models import Constants



class CustomWP(WaitPage):
    template_name = Constants.wait_page_template

    title_text = Constants.custom_title_text

    def vars_for_template(self):
        return {'body_text': Constants.custom_body_text}


page_sequence = [CustomWP]
