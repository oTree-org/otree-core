__doc__ = """This module contains many of pTree's internals.
The view classes in this module are just base classes, and cannot be called from a URL.
You should inherit from these classes and put your view class in your game directory (under "games/")
Or in the other view file in this directory, which stores shared concrete views that have URLs."""

from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, Http404, HttpResponseRedirect
import django.http
from django.core.context_processors import csrf
import random

from os.path import split, dirname, abspath

import vanilla

import ptree.models.common
import ptree.models.participants

import ptree.forms
from ptree.models.common import Symbols

REDIRECT_TO_PAGE_USER_SHOULD_BE_ON_URL = '/shared/RedirectToPageUserShouldBeOn/'

def get_parent_directory_name(_file_):
    return split(dirname(abspath(_file_)))[1]

class View(vanilla.View):
    """Base class for pTree views.
    Takes care of:
    - retrieving model classes and objects automatically,
    so you can access self.treatment, self.match, self.participant, etc.
    """

    def load_classes(self):
        """This loads from cookies"""
        
        self.ExperimentClass = self.request.session.get(Symbols.ExperimentClass)
        self.TreatmentClass = self.request.session.get(Symbols.TreatmentClass)
        self.ParticipantClass = self.request.session.get(Symbols.ParticipantClass)
        self.MatchClass = self.request.session.get(Symbols.MatchClass)


    def load_objects(self):
        self.participant = get_object_or_404(self.ParticipantClass,
            code = self.request.session.get(Symbols.participant_code))

        # for convenience
        self.match = self.participant.match
        self.treatment = self.match.treatment
        self.experiment = self.treatment.experiment

    def save_objects(self):
        for obj in [self.match, self.participant]:
            if obj:
                obj.save()

    def dispatch(self, request, *args, **kwargs):
        self.load_classes()
        self.load_objects()
        return super(View, self).dispatch(request, *args, **kwargs)

    @classmethod
    def get_url_base(cls):
        # look for url_base attribute on ExperimentClass
        # if it's not part of a game, but rather a shared module etc, ExperimentClass won't exist.
        # in that case, url_base needs to be defined on the class.
        return getattr(cls, 'ExperimentClass', cls).url_base

    @classmethod
    def url(cls):
        return '/{}/{}/'.format(cls.get_url_base(), cls.__name__)

    @classmethod
    def url_pattern(cls):
        return r'^{}/{}/$'.format(cls.get_url_base(), cls.__name__)

    def page_the_user_should_be_on(self):
        return self.treatment.sequence_as_urls()[self.request.session[Symbols.current_view_index]]

    def redirect_to_page_the_user_should_be_on(self):
        """Redirect to where the participant should be,
        according to the view index we maintain in their cookies
        Useful if the participant tried to skip ahead,
        or if they hit the back button.
        We can put them back where they belong.
        """
        return HttpResponseRedirect(self.page_the_user_should_be_on())


class TemplateView(View, vanilla.TemplateView):
    def get_variables_for_template(self):
        """
        Should be implemented by subclasses
        Return a dictionary that contains the template context variables (see Django documentation)
        You don't need to include the form here; that is taken care of automatically.
        """

        return {}

    def get_context_data(self, **kwargs):

        context = super(TemplateView, self).get_context_data(**kwargs)

        context.update(self.get_variables_for_template())

        return context


class OldPage(object):
    """It's here so that classes that inherit from it can be loaded.
    Should be removed"""
    pass

class SequenceView(View):
    """
    View that manages its position in the match sequence.
    """

    @classmethod
    def url(cls, index):
        return '/{}/{}/{}/'.format(cls.get_url_base(), cls.__name__, index)

    @classmethod
    def url_pattern(cls):
        return r'^{}/{}/(\d+)/$'.format(cls.get_url_base(), cls.__name__)


    success_url = REDIRECT_TO_PAGE_USER_SHOULD_BE_ON_URL

    def is_displayed(self):
        """whether this view is displayed. This method can be overridden by child classes"""
        return True

    def dispatch(self, request, *args, **kwargs):
        self.load_classes()
        self.load_objects()
        self.current_view_index = int(args[0])
        # remove it since post() may not be able to accept args.
        args = args[1:]

        # if the participant shouldn't see this view, skip to the next
        if not self.is_displayed():
            self.request.session[Symbols.current_view_index] += 1
            return self.redirect_to_page_the_user_should_be_on()

        # if the participant tried to skip past a part of the experiment
        # (e.g. by typing in a future URL)
        if not self.user_is_on_right_page():
            # then bring them back to where they should be
            return self.redirect_to_page_the_user_should_be_on()
        return super(SequenceView, self).dispatch(request, *args, **kwargs)

    def get_variables_for_template(self):
        """
        Should be implemented by subclasses
        Return a dictionary that contains the template context variables (see Django documentation)
        You don't need to include the form here; that is taken care of automatically.
        """

        return {}

    def get_context_data(self, **kwargs):

        context = {}
        
        # jump to form on invalid submission
        if kwargs.has_key(Symbols.form_invalid):
            context[Symbols.form_invalid] = True
            kwargs.pop(Symbols.form_invalid)

        # this will add the form to the context
        # FIXME: parent class is just object; how does this work?
        context.update(super(SequenceView, self).get_context_data(**kwargs))
        
        # whatever else you specify that doesn't go in the form
        # (e.g. info we display to the participant)
        context.update(self.get_variables_for_template())

        # protection against CSRF attacks
        context.update(csrf(self.request))

        #context.update({'participant_resubmitted_last_form':
        #                self.request.session.get(Symbols.participant_resubmitted_last_form)})
        
        # we may or may not need this line.
        # strictly speaking, we shouldn't really be modifying the database on a GET request
        # but that is more general guidance than a strict rule
        self.save_objects()
        return context

    def get_form(self, data=None, files=None, **kwargs):
        """
        Given `data` and `files` QueryDicts, and optionally other named
        arguments, and returns a form.
        """
        kwargs.update({'participant': self.participant,
                       'match': self.match,
                       'treatment': self.treatment,
                       'experiment': self.experiment,
                       'request': self.request})

        cls = self.get_form_class()
        return cls(data=data, files=files, **kwargs)

    def after_valid_form_submission(self, form):
        """Should be implemented by subclasses as necessary"""
        pass

    def form_valid(self, form):
        self.after_valid_form_submission(form)
        self.save_objects()
        if self.current_view_index == self.request.session[Symbols.current_view_index]:
            self.request.session[Symbols.current_view_index] += 1
        return super(SequenceView, self).form_valid(form)

    def form_invalid(self, form):
        """

        """
        return self.render_to_response(self.get_context_data(form=form, form_invalid = True ))

    def user_is_on_right_page(self):
        """Will detect if a participant tried to access a page they didn't reach yet,
        for example if they know the URL to the redemption code page,
        and try typing it in so they don't have to play the whole game.
        We should block that."""

        return self.request.path == self.page_the_user_should_be_on()


class UpdateView(SequenceView, vanilla.UpdateView):
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
        #
        # do this as soon as i get a chance
        # actually, since i may want to deprecate FormView, I may want to keep this in.
        # but if a person uses form field validation, they will have to access cleaned_data, right?

        form.save(commit = True)
        return super(UpdateView, self).form_valid(form)

    def get_object(self):
        
        """FIXME: need a more general way of handling this.
        or just document that you can only modify your match or participant.
        This is kind of a hack."""
        Cls = self.form_class.Meta.model
        if Cls == self.MatchClass:
            return self.match
        elif Cls == self.ParticipantClass:
            return self.participant
        else:
            # see if it's something that points to participant with a GenericForeignKey.
            # Assumes the generic relation is set up with the default object_id and content_type attributes.
            return Cls.objects.get(object_id=self.participant.id,
                                   content_type=ContentType.objects.get_for_model(self.participant))

class CreateView(SequenceView, vanilla.CreateView):
    """Must be used with AuxiliaryModels"""
    def form_valid(self, form):
        """If we're creating a new object (like a questionnaire),
        we want to associate it with the participant or the match"""
        obj = form.save(commit=False)
        if hasattr(obj, 'participant'):
            obj.participant = self.participant
        if hasattr(obj, 'match'):
            obj.match = self.match
        obj.save()
        return super(CreateView, self).form_valid(form)

class FormView(SequenceView, vanilla.FormView, View):
    """If you can't use a ModelForm, e.g. the data in the form should not be saved to the database,
    then you can use this as a fallback.
    Not emphasizing this in pTree documentation.
    """
    form_class = ptree.forms.NonModelForm

class GetTreatmentOrParticipant(vanilla.View):
    """
    The first View when participants visit a site.
    Doesn't have any UI.
    Just looks up the participant,
    decides what Treatment to randomize them to,
    and redirects to that Treatment.
    """

    def get(self, request, *args, **kwargs):
        # clear all cookies, since they can cause problems if the participant has played a previous game.

        self.request.session.clear()

        participant_code = self.request.GET.get(Symbols.participant_code)
        treatment_code = self.request.GET.get(Symbols.treatment_code)

        # need at least one
        assert participant_code or treatment_code

        if participant_code:
            self.participant = get_object_or_404(self.ParticipantClass, code = participant_code)

            # in your mTurk experiment you can append the assignmentId to the URL with JavaScript.
            self.participant.mturk_assignment_id = self.request.GET.get('assignmentId')

            self.experiment = self.participant.experiment

            # block re-randomization.
            # if the participant already got past the start view, they have had a match assigned to them.
            # this check is for participants who started to play the game,
            # but abandoned or hit the back button and re-entered the URL.
            # we don't want participants to be assigned to a different treatment when they re-visit the URL
            # because they might want to get a treatment that pays more money
            if self.participant.match:
                self.treatment = self.participant.match.treatment
            else:
                self.treatment = self.experiment.pick_treatment_for_incoming_participant()
        else:
            # demo mode
            self.treatment = get_object_or_404(self.TreatmentClass, code=treatment_code)
            self.experiment = self.treatment.experiment

            if self.request.GET[Symbols.demo_code] == self.experiment.demo_code:
                self.participant = self.ParticipantClass.objects.filter(experiment=self.experiment,
                                                            has_visited=False)[0]

        self.participant.has_visited = True
        self.participant.save()
        self.request.session[Symbols.participant_code] = self.participant.code
        self.request.session[Symbols.treatment_code] = self.treatment.code

        return HttpResponseRedirect('/{}/StartTreatment/{}/'.format(self.experiment.url_base, 0))

    @classmethod
    def get_url_base(cls):
        """urls.py requires that each view know its own URL.
        a URL base is the first part of the path, usually the name of the game"""
        return cls.ExperimentClass.url_base

    @classmethod
    def url(cls):
        """What the URL looks like, so we can redirect to it"""
        return '/{}/{}/'.format(cls.get_url_base(), cls.__name__)

    @classmethod
    def url_pattern(cls):
        """URL pattern regular expression, as required by urls.py"""
        return r'^{}/{}/$'.format(cls.get_url_base(), cls.__name__)

class StartTreatment(FormView):
    """Start page. Each game should have a Start view that inherits from this.
    This is not a modelform, because it can be used with many models.
    """

    form_class = ptree.forms.StartForm
    template_name = 'Start.html'

    def load_classes(self):
        """Don't want to load from cookies"""

    def load_objects(self):
        self.match = None

        self.participant = get_object_or_404(self.ParticipantClass,
                                             code = self.request.session[Symbols.participant_code])
        self.treatment = get_object_or_404(self.TreatmentClass,
                                           code = self.request.session[Symbols.treatment_code])
        self.experiment = self.participant.experiment

    def persist_classes(self):
        """We need these classes so that we can load the objects.
        We need to store it in cookies,
        rather than relying on each View knowing its Experiment, Treatment, etc.
        Although this is the case with the views in the games (which inherit from their Start view),
        some Views are in a shared module and therefore can be bound to different Experiments, Treatments, etc.
        """

        self.request.session[Symbols.ExperimentClass] = self.ExperimentClass
        self.request.session[Symbols.TreatmentClass] = self.TreatmentClass
        self.request.session[Symbols.ParticipantClass] = self.ParticipantClass
        self.request.session[Symbols.MatchClass] = self.MatchClass

    def dispatch(self, request, *args, **kwargs):
        self.request.session[Symbols.current_view_index] = self.request.session.get(Symbols.current_view_index, 0)

        return super(StartTreatment, self).dispatch(request, *args, **kwargs)

    def get_variables_for_template(self):

        # Setting a test cookie to see if there will be problems with the participant's browser.        
        self.request.session.set_test_cookie() 
        
        # persist classes so that other views can access them,
        # even if those classes are not a class attribute.
        self.persist_classes()

        return {}

    def after_valid_form_submission(self, form):
        if self.participant.ip_address == None:
            self.participant.ip_address = self.request.META['REMOTE_ADDR']
        if self.participant.name == None:
            self.participant.name = form.cleaned_data.get('name')
        
        # Checking if I was able to put a cookie in the participant's browser
        if self.request.session.test_cookie_worked():
            self.request.session.delete_test_cookie()
        else:
            # FIXME: we should tell the participant there was a problem with cookies
            raise Http404()

        self.configure_match()

    def configure_match(self):
        """
        Find the participant and associate him with an existing or new match.
        """

        # if participant already has a match, use that.
        if self.participant.match:
            self.match = self.participant.match
        # otherwise, try finding an open match, or create a new match.
        else:
            self.match = self.next_open_match() or self.create_match()
            self.add_participant_to_match()
            
        assert self.match
        assert self.match.treatment

        # persist match so it can be loaded in load_objects
        self.request.session[Symbols.match_id] = self.match.pk

    def next_open_match(self):
        try:
            return self.MatchClass.objects.next_open_match(self.request)
        except StopIteration:
            return None

    def create_match(self):
        match = self.MatchClass(treatment = self.treatment)
        # need to save it before you assign the participant.match ForeignKey
        match.save()
        return match

    def add_participant_to_match(self):
        self.participant.index = self.match.participant_set.count()
        self.participant.match = self.match

class StartTreatmentInTwoPersonAsymmetricGame(StartTreatment):
    """
    For convenience, we give asymmetric 2 participant games a participant_1 and participant_2 attributes.
    """

    def add_participant_to_match(self):
        self.participant.index = self.match.participant_set.count()
        self.participant.match = self.match
        if self.participant.index == 0:
            self.match.participant_1 = self.participant
        elif self.participant.index == 1:
            self.match.participant_2 = self.participant
