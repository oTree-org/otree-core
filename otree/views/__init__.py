#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Public API

"""

from importlib import import_module


# NOTE: this imports the following submodules and then subclasses several
# classes
# importing is done via import_module rather than an ordinary import.
# The only reason for this is to hide the base classes from IDEs like PyCharm,
# so that those members/attributes don't show up in autocomplete,
# including all the built-in django fields that an ordinary oTree programmer
# will never need or want.
# if this was a conventional Django project I wouldn't do it this way,
# but because oTree is aimed at newcomers who may need more assistance from
# their IDE,
# I want to try this approach out.
# this module is also a form of documentation of the public API.

abstract = import_module('otree.views.abstract')


class WaitPage(abstract.InGameWaitPage):

    wait_for_all_groups = False

    def body_text(self):
        return super(WaitPage, self).body_text()

    def title_text(self):
        return super(WaitPage, self).title_text()

    def after_all_players_arrive(self):
        return super(WaitPage, self).after_all_players_arrive()


class Page(abstract.PlayerUpdateView):

    def vars_for_template(self):
        return super(Page, self).vars_for_template()

    def before_next_page(self):
        return super(Page, self).before_next_page()

    def is_displayed(self):
        return super(Page, self).is_displayed()

    template_name = None

    # prefix with "form_" so that it's clear these refer to the form
    # otherwise someone might confuse 'fields' with vars_for_template
    form_model = abstract.PlayerUpdateView.model
    form_fields = abstract.PlayerUpdateView.fields

    timeout_seconds = None
    timeout_submission = {}
