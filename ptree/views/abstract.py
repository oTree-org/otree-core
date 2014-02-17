__doc__ = """This module contains many of pTree's internals.
The view classes in this module are just base classes, and cannot be called from a URL.
You should inherit from these classes and put your view class in your game directory (under "games/")
Or in the other view file in this directory, which stores shared concrete views that have URLs."""

import time
import logging
from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.conf import settings
import extra_views
import vanilla
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache, cache_control
from django.utils.translation import ugettext as _
from django.forms.models import model_to_dict

import ptree.constants as constants
from ptree.forms import StubModelForm, ExperimenterStubModelForm
import ptree.sessionlib.models as seq_models
import ptree.sessionlib.models
import ptree.common
import ptree.models.participants
import ptree.user.models


# Get an instance of a logger
logger = logging.getLogger(__name__)

REDIRECT_TO_PAGE_USER_SHOULD_BE_ON_URL = '/shared/RedirectToPageUserShouldBeOn/'

class PTreeMixin(object):
    """Base mixin class for pTree views.
    Takes care of:
    - retrieving model classes and objects automatically,
    so you can access view.treatment, self.match, self.participant, etc.
    """

    def load_classes(self):
        """
        Even though we only use ParticipantClass in load_objects,
        we use {Match/Treatment/Subsession}Class elsewhere.
        """
        self.SubsessionClass = self.request.session.get(constants.SubsessionClass)
        self.TreatmentClass = self.request.session.get(constants.TreatmentClass)
        self.ParticipantClass = self.request.session.get(constants.ParticipantClass)
        self.MatchClass = self.request.session.get(constants.MatchClass)
        self.UserClass = self.request.session.get(constants.UserClass)

    def load_user(self):
        code = self.request.session.get(constants.user_code)
        try:
            self.user = get_object_or_404(self.UserClass, code=code)
        except ValueError:
            raise Http404("This user ({}) does not exist in the database. Maybe the database was recreated.".format(code))
        self.subsession = self.user.subsession
        self.session = self.user.session
        self.session_user = self.user.session_user

    def save_objects(self):
        for obj in self.objects_to_save():
            if obj:
                obj.save()

    @classmethod
    def get_name_in_url(cls):
        # look for name_in_url attribute on SubsessionClass
        # if it's not part of a game, but rather a shared module etc, SubsessionClass won't exist.
        # in that case, name_in_url needs to be defined on the class.
        return getattr(cls, 'SubsessionClass', cls).name_in_url


    def redirect_to_page_the_user_should_be_on(self):
        """Redirect to where the participant should be,
        according to the view index we maintain in their cookies
        Useful if the participant tried to skip ahead,
        or if they hit the back button.
        We can put them back where they belong.
        """
        return HttpResponseRedirect(self.page_the_user_should_be_on())

    def variables_for_template(self):
        return {}

    def get_context_data(self, **kwargs):
        context = {}
        context.update(self.variables_for_template())
        return context

    def page_the_user_should_be_on(self):
        if self.session_user.index_in_subsessions > self.subsession.index_in_subsessions:
            users = self.session_user.users()
            try:
                return users[self.session_user.index_in_subsessions].start_url()
            except IndexError:
                from ptree.views.concrete import OutOfRangeNotification
                return OutOfRangeNotification.url()
        return self.user.pages_as_urls()[self.user.index_in_pages]

class LoadClassesAndUserMixin(object):

    def dispatch(self, request, *args, **kwargs):
        self.load_classes()
        self.load_user()
        return super(LoadClassesAndUserMixin, self).dispatch(request, *args, **kwargs)

class NonSequenceUrlMixin(object):
    @classmethod
    def url(cls):
        return '/{}/{}/'.format(cls.get_name_in_url(), cls.__name__)

    @classmethod
    def url_pattern(cls):
        return r'^{}/{}/$'.format(cls.get_name_in_url(), cls.__name__)


class ParticipantMixin(object):

    def load_objects(self):
        self.load_user()
        self.participant = self.user
        self.x = self.user
        self.match = self.participant.match
        # 2/11/2014: match may be undefined because the participant may be at a waiting screen
        # before experimenter assigns to a match & treatment.
        self.treatment = self.participant.treatment

    def objects_to_save(self):
        return [self.match, self.participant, self.participant.session_participant]

class ExperimenterMixin(object):


    def load_objects(self):
        self.load_user()

    def objects_to_save(self):
        return [self.user, self.subsession, self.session_user]

class WaitPageMixin(object):

    class PageActions:
        show = 'show'
        skip = 'skip'
        wait = 'wait'

    def show_skip_wait(self):
        return self.PageActions.show

    def validated_show_skip_wait(self):
        page_action = self.show_skip_wait()
        if not page_action in [self.PageActions.show, self.PageActions.skip, self.PageActions.wait]:
            raise ValueError('show_skip_wait() must return one of the following: [self.PageActions.show, self.PageActions.skip, self.PageActions.wait]')
        return page_action

    # TODO: this is intended to be in the user's project, not part of pTree core.
    # but maybe have one in pTree core as a fallback in case the user doesn't have it.
    wait_page_template_name = 'ptree/WaitPage.html'

    def wait_page_body_text(self):
        pass

    def wait_page_title_text(self):
        pass

    def request_is_from_wait_page(self):
        return self.request.is_ajax() and self.request.GET.get(constants.check_if_wait_is_over) == constants.get_param_truth_value

    def response_to_wait_page(self, page_action):
        no_more_wait = page_action != self.PageActions.wait
        return HttpResponse(int(no_more_wait))

    def wait_page_request_url(self):
        return '{}?{}={}'.format(
            self.request.path,
            constants.check_if_wait_is_over,
            constants.get_param_truth_value
        )

class SequenceMixin(PTreeMixin, WaitPageMixin):
    """
    View that manages its position in the match sequence.
    for both participants and experimenters
    """

    @classmethod
    def url(cls, index):
        return '/{}/{}/{}/'.format(cls.get_name_in_url(), cls.__name__, index)

    @classmethod
    def url_pattern(cls):
        return r'^{}/{}/(\d+)/$'.format(cls.get_name_in_url(), cls.__name__)

    success_url = REDIRECT_TO_PAGE_USER_SHOULD_BE_ON_URL

    def time_limit_in_seconds(self):
        return None

    def has_time_limit(self):
        return bool(self.time_limit_in_seconds())

    def set_time_limit(self, context):
        page_expiration_times = self.request.session[constants.page_expiration_times]
        if page_expiration_times.has_key(self.index_in_pages):
            page_expiration_time = page_expiration_times[self.index_in_pages]
            if page_expiration_time is None:
                remaining_seconds = None
            else:
                remaining_seconds = max(0, int(page_expiration_times[self.index_in_pages] - time.time()))
        else:
            remaining_seconds = self.time_limit_in_seconds()

            if remaining_seconds is None:
                page_expiration_times[self.index_in_pages] = None
            elif remaining_seconds > 0:
                page_expiration_times[self.index_in_pages] = time.time() + remaining_seconds
            else:
                raise ValueError("Time limit must be None or a positive number.")

        print 'set: {}'.format(page_expiration_times)
        if remaining_seconds is not None:
            minutes_component, seconds_component = divmod(remaining_seconds, 60)
        else:
            minutes_component, seconds_component = None, None

        time_limit_parameters = {
            constants.time_limit_minutes_component: str(minutes_component),
            constants.time_limit_seconds_component: str(seconds_component).zfill(2),
            constants.time_limit_in_seconds: remaining_seconds,
        }

        self.request.session[constants.page_expiration_times] = page_expiration_times
        context.update(time_limit_parameters)



    def get_time_limit_was_exceeded(self):
        page_expiration_times = self.request.session[constants.page_expiration_times]
        print 'get: {}'.format(page_expiration_times)
        page_expiration_time = page_expiration_times[self.index_in_pages]

        if page_expiration_time is None:
            return False
        return time.time() > (page_expiration_time + settings.TIME_LIMIT_GRACE_PERIOD_SECONDS)

    def timer_message(self):
        pass

    @method_decorator(never_cache)
    @method_decorator(cache_control(must_revalidate=True, max_age=0, no_cache=True, no_store = True))
    def dispatch(self, request, *args, **kwargs):
        try:
            self.load_classes()
            self.load_objects()
            self.index_in_pages = int(args[0])
            # remove it since post() may not be able to accept args.
            args = args[1:]

            # if the participant tried to skip past a part of the subsession
            # (e.g. by typing in a future URL)
            # or if they hit the back button to a previous subsession in the sequence.
            if not self.user_is_on_right_page():
                # then bring them back to where they should be
                return self.redirect_to_page_the_user_should_be_on()

            # by default it's false (e.g. for GET requests), but can be set to True in post() method
            self.time_limit_was_exceeded = False

            page_action = self.validated_show_skip_wait()

            if self.request_is_from_wait_page():
                response = self.response_to_wait_page(page_action)

            else:
                # if the participant shouldn't see this view, skip to the next
                if page_action == self.PageActions.skip:
                    self.z = self.user
                    self.update_indexes_in_sequences()
                    return self.redirect_to_page_the_user_should_be_on()

                if page_action == self.PageActions.wait:
                    return self.wait_page_response()
                response = super(SequenceMixin, self).dispatch(request, *args, **kwargs)
            self.session_user.last_request_succeeded = True
            self.session_user.save()
            return response
        except Exception, e:
            if hasattr(self, 'user'):
                user_info = 'user: {}'.format(model_to_dict(self.user))
                if hasattr(self, 'session_user'):
                    self.session_user.last_request_succeeded = False
                    self.session_user.save()
            else:
                user_info = '[user undefined]'
            diagnostic_info = (
                'is_ajax: {}'.format(self.request.is_ajax()),
                'user: {}'.format(user_info),
            )

            e.args += diagnostic_info
            raise

    def wait_page_response(self):
        return render_to_response(
            self.wait_page_template_name,
            {
                'SequenceViewURL': self.wait_page_request_url(),
                'debug_values': self.get_debug_values() if settings.DEBUG else None,
                'wait_page_body_text': self.wait_page_body_text(),
                'wait_page_title_text': self.wait_page_title_text()
            }
        )


    def post(self, request, *args, **kwargs):
        self.time_limit_was_exceeded = self.get_time_limit_was_exceeded()
        return super(SequenceMixin, self).post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):

        context = {'form': kwargs['form']}
        context.update(self.variables_for_template())
        context['timer_message'] = self.timer_message()

        if settings.DEBUG:
            context[constants.debug_values] = self.get_debug_values()

        self.set_time_limit(context)
        self.save_objects()
        return context

    def get_form(self, data=None, files=None, **kwargs):
        """
        Given `data` and `files` QueryDicts, and optionally other named
        arguments, and returns a form.
        """
        kwargs.update(self.get_extra_form_kwargs())
        cls = self.get_form_class()
        return cls(data=data, files=files, **kwargs)


    def after_valid_form_submission(self):
        """Should be implemented by subclasses as necessary"""
        pass

    def post_processing_on_valid_form(self, form):
        # form.save will also get called by the super() method, so this is technically redundant.
        # but it means that you don't need to access cleaned_data in after_valid_form_submission,
        # which is a little more user friendly.
        form.save(commit = True)

    def form_valid(self, form):
        self.form = form
        # 2/17/2014: moved post_processing before after_valid_form_submission.
        # that way, the object is up to date before the user's code is run.
        # otherwise, i don't see the point of saving twice.
        self.post_processing_on_valid_form(form)
        self.after_valid_form_submission()
        self.update_indexes_in_sequences()
        self.save_objects()
        return super(SequenceMixin, self).form_valid(form)

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

    def update_indexes_in_sequences(self):

        if self.index_in_pages == self.user.index_in_pages:
            self.user.index_in_pages += 1
            if self.user.index_in_pages >= len(self.user.pages_as_urls()):
                if self.subsession.index_in_subsessions == self.session_user.index_in_subsessions:
                    self.session_user.index_in_subsessions += 1
            self.user.save()
            self.session_user.save()

class ParticipantSequenceMixin(SequenceMixin):
    """for participants"""

    def get_debug_values(self):
        try:
            match_id = self.match.pk
        except:
            match_id = ''
        return [('Index among participants in match', self.participant.index_among_participants_in_match),
                ('Participant', self.participant.pk),
                ('Match', match_id),
                ('Treatment', self.treatment.pk),
                ('Subsession code', self.subsession.code),]


    def get_extra_form_kwargs(self):
        return {'participant': self.participant,
               'match': self.match,
               'treatment': self.treatment,
               'subsession': self.subsession,
               'request': self.request,
               'session': self.session,
               'time_limit_was_exceeded': self.time_limit_was_exceeded}

class ExperimenterSequenceMixin(SequenceMixin):

    def get_debug_values(self):
        return [('Subsession code', self.subsession.code),]

    def get_extra_form_kwargs(self):
        return {'subsession': self.subsession,
               'request': self.request,
               'session': self.session,
               'time_limit_was_exceeded': self.time_limit_was_exceeded}

class BaseView(PTreeMixin, NonSequenceUrlMixin, vanilla.View):
    """
    A basic view that provides no method implementations.
    """
    pass


class ParticipantUpdateView(ParticipantSequenceMixin, ParticipantMixin, vanilla.UpdateView):

    # if form_class is not provided, we use an empty form based on StubModel.
    form_class = StubModelForm

    def get_object(self):
        Cls = self.get_form_class().Meta.model
        if Cls == self.MatchClass:
            return self.match
        elif Cls == self.ParticipantClass:
            return self.participant
        elif Cls == seq_models.StubModel:
            return seq_models.StubModel.objects.all()[0]
        else:
            # For AuxiliaryModels
            return Cls.objects.get(object_id=self.participant.id,
                                   content_type=ContentType.objects.get_for_model(self.participant))

class ExperimenterUpdateView(ExperimenterSequenceMixin, ExperimenterMixin, vanilla.UpdateView):
    form_class = ExperimenterStubModelForm

    def get_object(self):
        Cls = self.get_form_class().Meta.model
        if Cls == self.SubsessionClass:
            return self.subsession
        elif Cls == seq_models.StubModel:
            return seq_models.StubModel.objects.all()[0]


class ParticipantCreateView(ParticipantSequenceMixin, vanilla.CreateView):
    def post_processing_on_valid_form(self, form):
        instance = form.save(commit=False)
        if hasattr(instance, 'participant'):
            instance.participant = self.participant
        if hasattr(instance, 'match'):
            instance.match = self.match
        instance.save()

class CreateView(ParticipantCreateView):
    pass

class ModelFormSetMixin(object):
    extra = 0

    def after_valid_form_submission(self, instance):
        """2/17/2014: this needs to take an extra argument of either the form or the instance,
        since it needs somehow to access the particular instance.
        (we can't use self.form because there are multiple forms)
        we could either pass the form or the instance.
        the instance is the one that will get used most frequently,
        but you can get form.instance but not vice versa.
        or have both args? (self, form, instance)
        will people ever want the form?
        hmmm, i don't know why someone would want the form rather than the instance.
        so for now, i will try just the instance.
        """

    def formset_valid(self, formset):
        formset.save()
        for form in formset:
            self.post_processing_on_valid_form(form)
            self.after_valid_form_submission(form.instance)
            form.instance.save()
        # 2/17/2014: I think there should be both a after_valid_formset_submission
        # (for more global actions)
        # and after_valid_form_submission (for items specific to the form)
        # but people are going to confuse the name, and write global code in after_valid_form_submission
        # i should give it a more distinct name.
        # or maybe tell people to iterate through self.object_list in after_valid_formset_submission?
        # (they will have to remember to save the objects)
        # for now, just rely on object_list until there is a need for a special method.
        self.after_valid_formset_submission()
        self.update_index_in_pages()
        self.save_objects()
        return super(ModelFormSetMixin, self).formset_valid(formset)

    def after_valid_formset_submission(self):
        pass

class CreateMultipleView(extra_views.ModelFormSetView, ParticipantCreateView):
    pass

class UpdateMultipleView(extra_views.ModelFormSetView, ParticipantUpdateView):
    pass

class ExperimenterUpdateMultipleView(ModelFormSetMixin, ExperimenterSequenceMixin, extra_views.ModelFormSetView):
    pass

class InitializeParticipantOrExperimenter(NonSequenceUrlMixin, vanilla.View):

    def initialize_time_limits(self):
        self.request.session[constants.page_expiration_times] = {}

    def persist_classes(self):
        """We need these classes so that we can load the objects.
        We need to store it in cookies,
        rather than relying on each View knowing its Subsession, Treatment, etc.
        Although this is the case with the views in the games (which inherit from their Start view),
        some Views are in a shared module and therefore can be bound to different Subsessions, Treatments, etc.
        """

        self.request.session[constants.SubsessionClass] = self.SubsessionClass
        self.request.session[constants.TreatmentClass] = self.TreatmentClass
        self.request.session[constants.ParticipantClass] = self.ParticipantClass
        self.request.session[constants.MatchClass] = self.MatchClass
        self.request.session[constants.UserClass] = self.ParticipantClass

class InitializeParticipant(InitializeParticipantOrExperimenter):
    """
    The first View when participants visit a site.
    Doesn't have any UI.
    Just looks up the participant,
    decides what Treatment to randomize them to,
    and redirects to that Treatment.
    """

    @classmethod
    def get_name_in_url(cls):
        """urls.py requires that each view know its own URL.
        a URL base is the first part of the path, usually the name of the game"""
        return cls.SubsessionClass.name_in_url

    def get(self, request, *args, **kwargs):
        self.request.session.clear()
        self.initialize_time_limits()

        user_code = self.request.GET.get(constants.user_code)

        self.user = get_object_or_404(self.ParticipantClass, code = user_code)
        # self.user is a generic name for self.participant
        # they are the same thing, but we use 'user' wherever possible
        # so that the code can be copy pasted to experimenter code
        self.participant = self.user
        self.subsession = self.participant.subsession

        self.user.visited = True
        self.user.time_started = datetime.now()

        self.user.save()
        self.request.session[constants.user_code] = self.user.code

        self.UserClass = self.ParticipantClass
        self.persist_classes()

        import ptree.views.concrete
        return HttpResponseRedirect(ptree.views.concrete.WaitUntilAssignedToMatch.url(0))

    def get_next_participant_in_subsession(self):
        try:
            return self.ParticipantClass.objects.filter(
                subsession=self.subsession,
                visited=False)[0]
        except IndexError:
            raise IndexError("No Participant objects left in the database to assign to new visitor.")

