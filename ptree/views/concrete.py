__doc__ = """This module contains views that are shared across many game types. 
They are ready to be included in your  Just import this module,
and include these classes in your Treatment's sequence() method."""

from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.core.urlresolvers import reverse
import django.http
from os.path import split, dirname, abspath
import os.path

import datetime
import re, os
from urllib import urlencode
import itertools

import django.views.generic.base
import django.views.generic.edit

from django.conf import settings

import ptree.views.abstract
import ptree.forms
import ayah


class View(object):
    URL_BASE = 'shared'

class Captcha(ptree.views.abstract.PageWithForm, View):
    """
    CAPTCHA from http://areyouahuman.com/.
    To use this, you first need to register an that site to get a publisher key and scoring key
    (see variables below)
    """
    template_name = 'ptree/Captcha.html'
    form_class = ptree.forms.CaptchaForm

    def get_template_variables(self):
        
        #FIXME: this should go in the form code
        ayah.configure(settings.AYAH_PUBLISHER_KEY, settings.AYAH_SCORING_KEY)
        captcha_html = ayah.get_publisher_html()
        
        return {'captcha_html': captcha_html, 
                'current_step': self.request.session.get('captchas_completed', 0) + 1,
                'total_steps': self.treatment.NUMBER_OF_CAPTCHAS}
     
class AssignPlayerAndMatch(ptree.views.abstract.AssignPlayerAndMatch, View):
    """Just a version of the parent class that is accessible from a URL"""
    pass

class AssignPlayerAndMatchAsymmetric2Player(ptree.views.abstract.AssignPlayerAndMatch, View):
    """
    For convenience, we gime asymmetric 2 player games a player_1 and player_2 attributes.
    """

    def add_player_to_match(self):
        self.player.index = self.match.player_set.count()
        self.player.match = self.match
        if self.player.index == 0:
            self.match.player_1 == self.player
        elif self.player.index == 1:
            self.match.player_2 == self.player

class RouteToCurrentPageInSequence(ptree.views.abstract.BaseView, View):
    """Redirect to this page when you can't do a redirect with the redirect_to_current_view method that increments the view index.
    Use cases: redirects from external websites, or from Django FormView, etc.
    """
    def get(self, request, *args, **kwargs):
        return self.redirect_to_current_view()

class RouteToNextPageInSequence(ptree.views.abstract.BaseView, View):
    """Use this when you need to go to the next index.
    But only use it in places where it's OK for the user to jump ahead as much as they want,
    since they might find a way to refresh this URL."""
    def get(self, request, *args, **kwargs):
        self.increment_current_view_index()
        return self.redirect_to_current_view()
