__doc__ = """This module contains many of pTree's internals. 
The view classes in this module are just base classes, and cannot be called from a URL.
You should inherit from these classes and put your view class in your game directory (under "games/")
Or in the other view file in this directory, which stores shared concrete views that have URLs."""

from django.db.models import Min
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.core.urlresolvers import reverse
import django.http
from django.core.context_processors import csrf
import random

from os.path import split, dirname, abspath

import datetime, smtplib, re, os
import os.path
from urllib import urlencode
import itertools

import django.views.generic.base
import django.views.generic.edit

from django.conf import settings

import ptree.models.common
import ptree.models.players
from ptree.models.common import IPAddressVisit

import abc
import ptree.forms

ROUTE_TO_CURRENT_VIEW = '/shared/RouteToCurrentPageInSequence/'

def get_parent_directory_name(_file_):
    return split(dirname(abspath(_file_)))[1]

class SessionKeys(object):
    """Key names used for request.session (to prevent string duplication)"""

    ExperimentClass = 'Experiment'
    TreatmentClass = 'Treatment'
    MatchClass = 'Match'
    PlayerClass = 'Player'
    
    match_id = 'match_id'

    player_code = 'player_code'
    experiment_code = 'experiment_code'
    treatment_code = 'treatment_code'

    nickname = 'nickname'

    current_view_index = 'current_view_index'

    ticket_to_next_page_has_been_used_list = 'ticket_to_next_page_has_been_used_list'

class BaseView(django.views.generic.base.View):
    """Base class for pTree views.
    Takes care of:
    - retrieving model classes and objects automatically
    - managing your position in the sequence of views
    so that you can easily access self.ExperimentClass, self.experiment, self.TreatmentClass, self.treatment, ...
    You should generally use this, unless your view occurs as soon as the user visits,
    and none of the objects have been created yet.
    
    """

    def load_classes(self):
        """This loads from cookies."""
        self.ExperimentClass = self.request.session.get(SessionKeys.ExperimentClass) or self.ExperimentClass
        self.TreatmentClass = self.request.session.get(SessionKeys.TreatmentClass) or self.TreatmentClass
        self.PlayerClass = self.request.session.get(SessionKeys.PlayerClass) or self.PlayerClass
        self.MatchClass = self.request.session.get(SessionKeys.MatchClass) or self.MatchClass

    def load_experiment(self):
        experiment_code = self.request.session.get(SessionKeys.experiment_code)
        if experiment_code:
            self.experiment = get_object_or_404(self.ExperimentClass, code=experiment_code)
        else:
            self.experiment = None

    def load_treatment(self):
        treatment_code = self.request.session.get(SessionKeys.treatment_code)
        if treatment_code:
            self.treatment = get_object_or_404(self.TreatmentClass, code=treatment_code)
        else:
            self.treatment = None
        
    def load_match(self):
        match_id = self.request.session.get(SessionKeys.match_id)
        if match_id:
            self.match = get_object_or_404(self.MatchClass, pk=match_id)
        else:
            self.match = None

    def load_player(self):
        player_code = self.request.session.get(SessionKeys.player_code)
        if player_code:
            self.player = get_object_or_404(self.PlayerClass, code = player_code)
        else:
            self.player = None

    def load_objects(self):
        self.load_experiment()
        self.load_treatment()
        self.load_match()
        self.load_player()

    def save_objects(self):
        for obj in [self.match, self.player]:
            if obj:
                obj.save()

    def dispatch(self, request, *args, **kwargs):
        self.load_classes()
        self.load_objects()
        return super(BaseView, self).dispatch(request, *args, **kwargs)

    def initialize_ticket_to_next_page_has_been_used_list(self):
        """Each level should allow you to increment the current view index only once"""
        
        self.request.session[SessionKeys.ticket_to_next_page_has_been_used_list] = [False] * (len(self.treatment.sequence()) - 1)
    
    def increment_current_view_index(self):
        
        # the indices of all views in the sequence whose URL match the current page's URL
        indices_of_current_page = [i for i, x in enumerate(self.treatment.sequence_as_urls()) 
                                       if x == self.request.path
                                          and i <= self.request.session[SessionKeys.current_view_index]]

        # see if any of them have an unused ticket, and use it.
        for i in indices_of_current_page:
            if self.request.session[SessionKeys.ticket_to_next_page_has_been_used_list][i] == False:
                self.request.session[SessionKeys.ticket_to_next_page_has_been_used_list][i] = True
                self.request.session[SessionKeys.current_view_index] += 1
                return
            
    def current_view(self):
        #print 'self.treatment.sequence(): {}'.format(self.treatment.sequence())
        #print 'self.request.session[SessionKeys.current_view_index]: {}'.format(self.request.session[SessionKeys.current_view_index])
        return self.treatment.sequence()[self.request.session[SessionKeys.current_view_index]].url()

    def user_skipped_a_page(self):
        """Will detect if a user tried to access a page they didn't reach yet,
        for example if they know the URL to the redemption code page,
        and try typing it in so they don't have to play the whole game.
        We should block that."""
        sequence_urls = self.treatment.sequence_as_urls()

        # if the index of the first occurrence in the list is ahead of where you should be,
        # then you must have gotten there erroneously.
        return (sequence_urls.index(self.request.path) > self.request.session[SessionKeys.current_view_index])

    def redirect_to_current_view(self):
        """Redirect to where the user should be,
        according to the view index we maintain in their cookies
        Useful if the user tried to skip ahead,
        or if they hit the back button.
        We can put them back where they belong.
        """
        return HttpResponseRedirect(self.current_view())

    @classmethod
    def url_base(cls):
        if hasattr(cls, 'ExperimentClass'):
            return cls.ExperimentClass.url_base
        else:
            # i.e. if it's not part of a game, but rather a shared module etc
            # then you need to set this manually
            return cls.url_base
        
    @classmethod
    def url(cls):
        return '/{}/{}/'.format(cls.url_base(), cls.__name__)

    @classmethod
    def url_pattern(cls):
        return r'^{}/{}/$'.format(cls.url_base(), cls.__name__)


class OldPage(object):
    """It's here so that classes that inherit from it can be loaded.
    Should be removed"""
    pass

class PageWithFormMixin(object):
    """
    Base class for most views.
    Abilities:
    - 
    - 
    
    """
    success_url = ROUTE_TO_CURRENT_VIEW

    def is_displayed(self):
        """whether this view is displayed. This method can be overridden by child classes"""
        return True

    def dispatch(self, request, *args, **kwargs):
        self.load_classes()
        self.load_objects()

        # if the user shouldn't see this view, skip to the next
        if not self.is_displayed():
            self.increment_current_view_index()
            return self.redirect_to_current_view()

        # if the user tried to skip past a part of the experiment
        # (e.g. by typing in a future URL)
        if self.user_skipped_a_page():
            # then bring them back to where they should be
            return HttpResponseRedirect(ROUTE_TO_CURRENT_VIEW)
        return super(PageWithFormMixin, self).dispatch(request, *args, **kwargs)

    def get_template_variables(self):
        """
        Should be implemented by subclasses
        Return a dictionary that contains the template context variables (see Django documentation)
        You don't need to include the form here; that is taken care of automatically.
        """

        return {}

    def get_context_data(self, **kwargs):

        context = {}
        
        # jump to form on invalid submission
        try:
            # take it out of kwargs before calling super()
            kwargs.pop('jump_to_form')
        except KeyError:
            context['jump_to_form'] = False
        else:
            context['jump_to_form'] = True

        # this will add the form to the context
        context += super(PageWithFormMixin, self).get_context_data(**kwargs)
        
        # whatever else you specify that doesn't go in the form
        # (e.g. info we display to the user)
        context.update(self.get_template_variables())

        # protection against CSRF attacks
        context.update(csrf(self.request))
        
        # we may or may not need this line.
        # strictly speaking, we shouldn't really be modifying the database on a GET request
        # but that is more general guidance than a strict rule
        self.save_objects()
        return context

    def get_form_kwargs(self):
        """
        Provides your form classes with access to the player, match, treatment, etc. objects
        So that they can have more dynamic rendering & validation behavior.
        """

        kwargs = super(PageWithFormMixin, self).get_form_kwargs()
        
        #TODO: maybe add experiment to this
        kwargs.update({'player': self.player,
                       'match': self.match,
                       'treatment': self.treatment,
                       'request': self.request})
        return kwargs

    def after_form_validates(self, form):
        """Should be implemented by subclasses as necessary"""
        pass

    def form_valid(self, form):
        self.after_form_validates(form)
        self.save_objects()
        self.increment_current_view_index()
        return super(PageWithFormMixin, self).form_valid(form)

    def form_invalid(self, form):
        """

        """
        return self.render_to_response(self.get_context_data(form=form, jump_to_form = True ))

class PageWithModelForm(PageWithFormMixin, django.views.generic.edit.UpdateView, BaseView):
    """For pages with a form whose values you want to save to the database.
    Try to inherit from this as much as you can.
    This is the bread and butter View of pTree.
    """
    
    form_class = None

    def form_valid(self, form):
        #FIXME: form.save will also get called by parent class, so this is being duplicated.
        # it prevents me from having to access the form attributes through cleaned_data.
        # But I think I should take it out since it's inconsistent with FormView,
        # and also non-standard.
        # do this as soon as i get a chance
        form.save(commit = True)
        return super(PageWithModelForm, self).form_valid(form)

    def get_object(self):
        """FIXME: need a more general way of handling this.
        This is kind of a hack."""
        cls = self.form_class.Meta.model
        if cls == self.MatchClass:
            return self.match
        elif cls == self.PlayerClass:
            return self.player


class PageWithForm(PageWithFormMixin, django.views.generic.FormView, BaseView):
    """If you can't use a ModelForm, e.g. the data in the form will not be saved to the database,
    then you can use this as a fallback."""
    form_class = ptree.forms.BlankForm


class Start(PageWithForm, BaseView):
    """Start page. Each game should have a Start view that inherits from this.
    This is not a modelform, because it can be used with many models.
    """
    

    form_class = ptree.forms.StartForm
    template_name = 'ptree/Start.html'

    def persist_classes(self):
        """We need these classes so that we can load the objects.
        We need to store it in cookies,
        rather than relying on each View knowing its Experiment, Treatment, etc.
        Although this is the case with the views in the games (which inherit from their Start view),
        some Views are in a shared module and therefore can be bound to different Experiments, Treatments, etc.
        """

        self.request.session[SessionKeys.ExperimentClass] = self.ExperimentClass
        self.request.session[SessionKeys.TreatmentClass] = self.TreatmentClass
        self.request.session[SessionKeys.PlayerClass] = self.PlayerClass
        self.request.session[SessionKeys.MatchClass] = self.MatchClass

    def dispatch(self, request, *args, **kwargs):
        self.load_objects()
        assert self.experiment
        assert self.treatment
        assert self.player

        return super(PageWithFormMixin, self).dispatch(request, *args, **kwargs)

    
    def get_template_variables(self):

        # Setting a test cookie to see if there will be problems with the user's browser.        
        self.request.session.set_test_cookie() 
        
        # persist classes so that other views can access them,
        # even if those classes are not a class attribute.
        self.persist_classes()
        
        # FIXME: why do we need this? We already call load_objects in dispatch()
        # self.load_objects()
        self.request.session[SessionKeys.current_view_index] = 0
        self.initialize_ticket_to_next_page_has_been_used_list()

        return {}

    def after_form_validates(self, form):
        if self.player.ip_address == None:
            self.player.ip_address = self.request.META['REMOTE_ADDR']
        if self.player.nickname == None:
            self.player.nickname = form.cleaned_data['nickname']
        
        # Checking if I was able to put a cookie in the user's browser
        if self.request.session.test_cookie_worked():
            self.request.session.delete_test_cookie()
        else:
            # FIXME: we should tell the user there was a problem with cookies
            raise Http404()

        self.request.session[SessionKeys.treatment_code] = self.treatment.code
        return {}
                
class AssignPlayerAndMatch(BaseView):
    """Find the player and associate him with an existing or new match.
    No UI to this View. Just redirects.
    """

    def get(self, request, *args, **kwargs):
        # objects loaded in dispatch. match usually will not exist, but will if a user hits the back button
        assert self.player 
        assert self.treatment
        assert self.experiment
        assert self.request.session[SessionKeys.current_view_index] == 1


        # if player already has a match, use that.
        if self.player.match:
            self.match = self.player.match
        # otherwise, try finding an open match, or create a new match.
        else:
            self.match = self.next_open_match() or self.create_match()
            self.add_player_to_match()
            
        assert self.match
        assert self.match.treatment

        self.save_objects()

        # persist match so it can be loaded in load_objects
        self.request.session[SessionKeys.match_id] = self.match.pk

        # redirect to next view
        self.increment_current_view_index()
        return self.redirect_to_current_view()


    def next_open_match(self):
        try:
            return self.MatchClass.objects.next_open_match(self.request)
        except StopIteration:
            return None

    def create_match(self):
        match = self.MatchClass(treatment = self.treatment)
        # need to save it before you assign the player.match ForeignKey
        match.save()
        return match

    def add_player_to_match(self):
        self.player.index = self.match.player_set.count()
        self.player.match = self.match

    
class PickTreatment(django.views.generic.base.View):
    """
    The first View when users visit a site.
    Doesn't have any UI.
    Just looks up the player,
    decides what Treatment to randomize them to,
    and redirects to that Treatment.
    """

    def load_player(self):
        player_code = self.request.session.get(SessionKeys.player_code)
        if player_code:
            self.player = get_object_or_404(self.PlayerClass, code = player_code)
        else:
            self.player = None

    def get(self, request, *args, **kwargs):
        # clear all cookies, since they can cause problems if the user has played a previous game.
        self.request.session.clear()
        
        # retrieve experiment
        experiment_code = self.request.GET['exp']
        experiment = get_object_or_404(self.ExperimentClass, code=experiment_code)

        # store for future access
        self.request.session[SessionKeys.experiment_code] = experiment_code
        
        # get the player object, so that we can see if the player already has been assigned to a treatment
        # this helps us prevent re-randomization
        self.request.session[SessionKeys.player_code] = self.request.GET['player']
        self.load_player()
        
        # player should exist after load_player since the object was created in advance, and its code was passed in the URL
        assert self.player

        # record their visit, and save it since this is GET.
        self.player.has_visited = True
        self.player.save()

        # if the user already got past the start view, they have had a match assigned to them.
        # this check is for users who started to play the game,
        # but abandoned or hit the back button and re-entered the URL.
        # we don't want users to be assigned to a different treatment when they re-visit the URL
        # because they might want to get a treatment that pays more money
        if self.player.match:
            treatment = self.player.match.treatment

            # a match has a treatment assigned on creation
            assert treatment != None
        else:
            if experiment.randomization_mode == self.ExperimentClass.INDEPENDENT:
                treatment = random.choice(experiment.treatment_set.all())
            elif experiment.randomization_mode == self.ExperimentClass.SMOOTHING:
                ## find the treatment with the fewest responses
                ## and assign to that one to even out the counts
                
                # lambda function to count the number of completed matches in a given treatment
                number_of_completed_matches = lambda treatment: len([match for match in treatment.matches() if match.is_finished()])

                # of all the treatments, what is the minimum number of matches completed?
                min_number_of_completed_matches = number_of_completed_matches(min(experiment.treatment_set.all(), key = number_of_completed_matches))

                # if there is a tie for lowest number, 
                # randomly pick from the treatments.
                treatment = random.choice([t for t in experiment.treatment_set.all() if number_of_completed_matches(t) == min_number_of_completed_matches])
        
        # store it so we can retrieve in Start.
        self.request.session[SessionKeys.treatment_code] = treatment.code
        
        # put treatment code in the URL, just for ease of troubleshooting.
        # we don't actually process this argument in the next view,
        # since we already stored it in cookies.
        # but it's convenient for troubleshooting to know what treatment you're in.
        return HttpResponseRedirect('/{}/Start/?{}={}'.format(experiment.url_base, SessionKeys.treatment_code, treatment.code))

    @classmethod
    def url_base(cls):
        """urls.py requires that each view know its own URL.
        a URL base is the first part of the path, usually the name of the game"""
        if hasattr(cls, 'ExperimentClass'):
            return cls.ExperimentClass.url_base
        else:
            # i.e. if it's not part of a game, but rather a shared module etc
            # then you need to set this manually
            return cls.url_base
        
    @classmethod
    def url(cls):
        """What the URL looks like, so we can redirect to it"""
        return '/{}/{}/'.format(cls.url_base(), cls.__name__)

    @classmethod
    def url_pattern(cls):
        """URL pattern regular expression, as required by urls.py"""
        return r'^{}/{}/$'.format(cls.url_base(), cls.__name__)
