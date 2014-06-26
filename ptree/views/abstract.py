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
from ptree.forms_internal import StubModelForm, ExperimenterStubModelForm
import ptree.sessionlib.models as seq_models
import ptree.sessionlib.models
import ptree.common

import ptree.user.models
import ptree.forms_internal
from ptree.user.models import Experimenter
import copy
import django.utils.timezone

from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
import vanilla
from django.utils.translation import ugettext as _
import ptree.sessionlib.models
from ptree.sessionlib.models import SessionParticipant


# Get an instance of a logger
logger = logging.getLogger(__name__)

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
        We don't need this as long as people have the correct mixins,
        but it's likely that people will forget to put the mixin.
        """

        self.SubsessionClass = self.request_session.get(constants.SubsessionClass)
        self.TreatmentClass = self.request_session.get(constants.TreatmentClass)
        self.ParticipantClass = self.request_session.get(constants.ParticipantClass)
        self.MatchClass = self.request_session.get(constants.MatchClass)
        self.UserClass = self.request_session.get(constants.UserClass)

    def load_user(self):
        code = self.request_session[constants.user_code]
        try:
            self.user = get_object_or_404(self.UserClass, code=code)
        except ValueError:
            raise Http404("This user ({}) does not exist in the database. Maybe the database was recreated.".format(code))
        self.subsession = self.user.subsession
        self.session = self.user.session

        # at this point, _session_user already exists, but we reassign this variable
        # the reason is that if we don't do this, there will be self._session_user, and
        # self.user._session_user, which will be 2 separate queries, and thus changes made to 1 object
        # will not be reflected in the other.
        self._session_user = self.user._session_user

    def save_objects(self):
        for obj in self.objects_to_save():
            if obj:
                obj.save()

    @classmethod
    def get_name_in_url(cls):
        # look for name_in_url attribute on SubsessionClass
        # if it's not part of a game, but rather a shared module etc, SubsessionClass won't exist.
        # in that case, name_in_url needs to be defined on the class.
        if hasattr(cls, 'z_models'):
            return cls.z_models.Subsession.name_in_url
        return cls.name_in_url

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
        context.update(self.variables_for_template() or {})
        return context

    def page_the_user_should_be_on(self):
        if self._session_user._index_in_subsessions > self.subsession._index_in_subsessions:
            users = self._session_user.users()
            try:
                return users[self._session_user._index_in_subsessions]._start_url()
            except IndexError:
                from ptree.views.concrete import OutOfRangeNotification
                return OutOfRangeNotification.url(self._session_user)
        return self.user._pages_as_urls()[self.user.index_in_pages]

    def get_request_session(self):
        return self.request.session[self._session_user.code]

def load_session_user(dispatch_method):
    def wrapped(self, request, *args, **kwargs):
        session_user_code = kwargs.pop(constants.session_user_code)
        user_type = kwargs.pop(constants.user_type)
        if user_type == constants.user_type_participant:
            SessionUserClass = ptree.sessionlib.models.SessionParticipant
        else:
            SessionUserClass = ptree.sessionlib.models.SessionExperimenter

        self._session_user = get_object_or_404(SessionUserClass, code = session_user_code)
        self.request_session = self.get_request_session().copy()
        response = dispatch_method(self, request, *args, **kwargs)
        self.request.session[self._session_user.code] = copy.deepcopy(self.request_session)
        return response
    return wrapped

class LoadClassesAndUserMixin(object):

    def dispatch(self, request, *args, **kwargs):
        self.load_classes()
        self.load_user()
        return super(LoadClassesAndUserMixin, self).dispatch(request, *args, **kwargs)

class NonSequenceUrlMixin(object):
    @classmethod
    def url(cls, session_user):
        return ptree.common.url(cls, session_user)

    @classmethod
    def url_pattern(cls):
        return ptree.common.url_pattern(cls, False)

class ParticipantMixin(object):

    def load_objects(self):
        self.load_user()
        self.participant = self.user
        self.match = self.participant.match
        # 2/11/2014: match may be undefined because the participant may be at a waiting screen
        # before experimenter assigns to a match & treatment.
        self.treatment = self.participant.treatment

    def objects_to_save(self):
        return [self.match, self.user, self._session_user]

class ExperimenterMixin(object):

    def load_objects(self):
        self.load_user()

    def objects_to_save(self):
        return [self.user, self.subsession, self._session_user] #+ self.subsession.participants() + self.subsession.matches() + self.subsession.treatments()

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

    def get_debug_values(self):
        pass

    def get_wait_page(self):
        response = render_to_response(
            self.wait_page_template_name,
            {
                'SequenceViewURL': self.wait_page_request_url(),
                'debug_values': self.get_debug_values() if settings.DEBUG else None,
                'wait_page_body_text': self.wait_page_body_text(),
                'wait_page_title_text': self.wait_page_title_text()
            }
        )
        response[constants.wait_page_http_header] = constants.get_param_truth_value
        return response


class SequenceMixin(PTreeMixin, WaitPageMixin):
    """
    View that manages its position in the match sequence.
    for both participants and experimenters
    """

    @classmethod
    def url(cls, session_user, index):
        return ptree.common.url(cls, session_user, index)

    @classmethod
    def url_pattern(cls):
        return ptree.common.url_pattern(cls, True)

    def time_limit_in_seconds(self):
        return None

    def has_time_limit(self):
        return bool(self.time_limit_in_seconds())

    def set_time_limit(self, context):
        page_expiration_times = self.request_session[constants.page_expiration_times]
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

        if remaining_seconds is not None:
            minutes_component, seconds_component = divmod(remaining_seconds, 60)
        else:
            minutes_component, seconds_component = None, None

        time_limit_parameters = {
            constants.time_limit_minutes_component: str(minutes_component),
            constants.time_limit_seconds_component: str(seconds_component).zfill(2),
            constants.time_limit_in_seconds: remaining_seconds,
        }

        self.request_session[constants.page_expiration_times] = page_expiration_times
        context.update(time_limit_parameters)



    def get_time_limit_was_exceeded(self):
        page_expiration_times = self.request_session[constants.page_expiration_times]
        page_expiration_time = page_expiration_times[self.index_in_pages]

        if page_expiration_time is None:
            return False
        return time.time() > (page_expiration_time + settings.TIME_LIMIT_GRACE_PERIOD_SECONDS)

    def timer_message(self):
        pass

    @method_decorator(never_cache)
    @method_decorator(cache_control(must_revalidate=True, max_age=0, no_cache=True, no_store = True))
    @load_session_user
    def dispatch(self, request, *args, **kwargs):
        try:
            self.load_classes()
            self.load_objects()

            if self.subsession._skip:
                self.update_index_in_subsessions()
                return self.redirect_to_page_the_user_should_be_on()

            self.index_in_pages = int(kwargs.pop(constants.index_in_pages))

            # if the participant tried to skip past a part of the subsession
            # (e.g. by typing in a future URL)
            # or if they hit the back button to a previous subsession in the sequence.
            if not self.user_is_on_right_page():
                # then bring them back to where they should be
                return self.redirect_to_page_the_user_should_be_on()

            self._session_user.current_page = self.__class__.__name__

            # by default it's false (e.g. for GET requests), but can be set to True in post() method
            self.time_limit_was_exceeded = False

            page_action = self.validated_show_skip_wait()
            self._session_user.is_on_wait_page = page_action == self.PageActions.wait

            if self.request_is_from_wait_page():
                response = self.response_to_wait_page(page_action)

            else:
                # if the participant shouldn't see this view, skip to the next
                if page_action == self.PageActions.skip:
                    self.update_indexes_in_sequences()
                    response = self.redirect_to_page_the_user_should_be_on()
                elif page_action == self.PageActions.wait:
                    response = self.get_wait_page()
                else:
                    response = super(SequenceMixin, self).dispatch(request, *args, **kwargs)
            self._session_user.last_request_succeeded = True
            self.save_objects()
            return response
        except Exception, e:

            if hasattr(self, 'user'):
                user_info = 'user: {}'.format(model_to_dict(self.user))
                if hasattr(self, '_session_user'):
                    self._session_user.last_request_succeeded = False
                    self._session_user.save()
            else:
                user_info = '[user undefined]'
            diagnostic_info = (
                'is_ajax: {}'.format(self.request.is_ajax()),
                'user: {}'.format(user_info),
            )

            e.args = (e.args[0] + '\nDiagnostic info: {}'.format(diagnostic_info),) + e.args[1:]
            raise



    def post(self, request, *args, **kwargs):
        # workaround to bug #18
        self.time_limit_was_exceeded = False #self.get_time_limit_was_exceeded()
        return super(SequenceMixin, self).post(request, *args, **kwargs)


    def get_context_data(self, **kwargs):
        context = {'form_or_formset': kwargs.get('form') or kwargs.get('formset') or kwargs.get('form_or_formset')}
        context.update(self.variables_for_template() or {})
        context['timer_message'] = self.timer_message()

        if settings.DEBUG:
            context[constants.debug_values] = self.get_debug_values()

        self.set_time_limit(context)
        return context

    def get_form(self, data=None, files=None, **kwargs):
        """
        Given `data` and `files` QueryDicts, and optionally other named
        arguments, and returns a form.
        """
        kwargs.update(self.get_extra_form_kwargs())
        cls = self.get_form_class()
        return cls(data=data, files=files, **kwargs)


    def post_processing_on_valid_form(self, form):
        pass

    def user_is_on_right_page(self):
        """Will detect if a participant tried to access a page they didn't reach yet,
        for example if they know the URL to the redemption code page,
        and try typing it in so they don't have to play the whole game.
        We should block that."""

        return self.request.path == self.page_the_user_should_be_on()

    def update_index_in_subsessions(self):
        if self.subsession._index_in_subsessions == self._session_user._index_in_subsessions:
            self._session_user._index_in_subsessions += 1

    def update_indexes_in_sequences(self):
        if self.index_in_pages == self.user.index_in_pages:
            self.user.index_in_pages += 1
            if self.user.index_in_pages >= len(self.user._pages_as_urls()):
                self.update_index_in_subsessions()

    def form_invalid(self, form):
        response = super(SequenceMixin, self).form_invalid(form)
        response[constants.redisplay_with_errors_http_header] = constants.get_param_truth_value
        return response

class ModelFormMixin(object):
    """mixin rather than subclass because we want these methods only to be first in MRO"""

    def after_valid_form_submission(self):
        """Should be implemented by subclasses as necessary"""
        pass

    def form_valid(self, form):
        self.form = form
        self.object = form.save()
        # 2/17/2014: moved post_processing before after_valid_form_submission.
        # that way, the object is up to date before the user's code is run.
        # otherwise, i don't see the point of saving twice.
        self.post_processing_on_valid_form(form)
        self.after_valid_form_submission()
        self.update_indexes_in_sequences()
        return HttpResponseRedirect(self._session_user.get_success_url())

class ModelFormSetMixin(object):
    """mixin rather than subclass because we want these methods only to be first in MRO"""
    extra = 0

    def get_formset(self, data=None, files=None, **kwargs):
        formset = super(ModelFormSetMixin, self).get_formset(data, files, **kwargs)
        # crispy forms: get the helper from the first form in the formset, and assign it to the whole formset
        if len(formset.forms) >= 1:
            formset.helper = formset.forms[0].helper
        else:
            formset.helper = ptree.forms_internal.FormHelper()
        return formset

    def after_valid_form_submission(self):
        pass

    def formset_valid(self, formset):
        self.object_list = formset.save()
        for form in formset:
            self.post_processing_on_valid_form(form)
        # 2/17/2014: I think there should be both a after_valid_formset_submission
        # (for more global actions)
        # and after_valid_form_submission (for items specific to the form)
        # but people are going to confuse the name, and write global code in after_valid_form_submission
        # i should give it a more distinct name.
        # or maybe tell people to iterate through self.object_list in after_valid_formset_submission?
        # (they will have to remember to save the objects)
        # for now, just rely on object_list until there is a need for a special method.
        self.after_valid_form_submission()
        self.update_indexes_in_sequences()
        return HttpResponseRedirect(self._session_user.get_success_url())


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
                ('Session code', self.session.code),]


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

class CreateAuxModelMixin(object):
    def post_processing_on_valid_form(self, form):
        instance = form.save(commit=False)
        if hasattr(instance, 'participant'):
            instance.participant = self.participant
        if hasattr(instance, 'match'):
            instance.match = self.match
        instance.save()

class ParticipantUpdateView(ModelFormMixin, ParticipantSequenceMixin, ParticipantMixin, vanilla.UpdateView):

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



class ExperimenterUpdateView(ModelFormMixin, ExperimenterSequenceMixin, ExperimenterMixin, vanilla.UpdateView):
    form_class = ExperimenterStubModelForm

    def get_object(self):
        Cls = self.get_form_class().Meta.model
        if Cls == self.SubsessionClass:
            return self.subsession
        elif Cls == seq_models.StubModel:
            return seq_models.StubModel.objects.all()[0]


class ParticipantCreateView(ModelFormMixin, ParticipantSequenceMixin, ParticipantMixin, CreateAuxModelMixin, vanilla.CreateView):
    """use case?"""
    pass

class ExperimenterCreateView(ModelFormMixin, ExperimenterSequenceMixin, ExperimenterMixin, CreateAuxModelMixin, vanilla.CreateView):
    pass

class ParticipantCreateMultipleView(ModelFormSetMixin, ParticipantSequenceMixin, ParticipantMixin, CreateAuxModelMixin, extra_views.ModelFormSetView):
    """incomplete. i need something like get_queryset"""

class ExperimenterCreateMultipleView(ModelFormSetMixin, ExperimenterSequenceMixin, ExperimenterMixin, CreateAuxModelMixin, extra_views.ModelFormSetView):
    """incomplete. i need something like get_queryset"""

class ParticipantUpdateMultipleView(ModelFormSetMixin, ParticipantSequenceMixin, ParticipantMixin, extra_views.ModelFormSetView):
    pass

class ExperimenterUpdateMultipleView(ModelFormSetMixin, ExperimenterSequenceMixin, ExperimenterMixin, extra_views.ModelFormSetView):
    pass

class InitializeParticipantOrExperimenter(NonSequenceUrlMixin, vanilla.View):

    @classmethod
    def get_name_in_url(cls):
        """urls.py requires that each view know its own URL.
        a URL base is the first part of the path, usually the name of the game"""
        return cls.z_models.Subsession.name_in_url

    def initialize_time_limits(self):
        self.request_session[constants.page_expiration_times] = {}

    def persist_classes(self):
        """We need these classes so that we can load the objects.
        We need to store it in cookies,
        rather than relying on each View knowing its Subsession, Treatment, etc.
        Although this is the case with the views in the games (which inherit from their Start view),
        some Views are in a shared module and therefore can be bound to different Subsessions, Treatments, etc.
        """

        self.request_session[constants.SubsessionClass] = self.z_models.Subsession
        self.request_session[constants.TreatmentClass] = self.z_models.Treatment
        self.request_session[constants.ParticipantClass] = self.z_models.Participant
        self.request_session[constants.MatchClass] = self.z_models.Match

    def get_request_session(self):
        return {}

    @load_session_user
    def dispatch(self, request, *args, **kwargs):
        return super(InitializeParticipantOrExperimenter, self).dispatch(request, *args, **kwargs)

class InitializeParticipant(InitializeParticipantOrExperimenter):
    """
    What if I merged this with WaitUntilAssigned?
    """

    def get(self, request, *args, **kwargs):
        self.request_session = {}
        self.initialize_time_limits()

        user_code = self.request.GET.get(constants.user_code)

        self.user = get_object_or_404(self.z_models.Participant, code = user_code)
        # self.user is a generic name for self.participant
        # they are the same thing, but we use 'user' wherever possible
        # so that the code can be copy pasted to experimenter code
        self.participant = self.user
        self.subsession = self.participant.subsession

        self.user.visited = True
        self.user.time_started = django.utils.timezone.now()

        self.user.save()
        self.request_session[constants.user_code] = self.user.code

        self.persist_classes()
        return HttpResponseRedirect(self.user._pages_as_urls()[0])

    def get_next_participant_in_subsession(self):
        try:
            return self.z_models.Participant.objects.filter(
                subsession=self.subsession,
                visited=False)[0]
        except IndexError:
            raise IndexError("No Participant objects left in the database to assign to new visitor.")

    def persist_classes(self):
        super(InitializeParticipant, self).persist_classes()
        self.request_session[constants.UserClass] = self.z_models.Participant

class InitializeExperimenter(InitializeParticipantOrExperimenter):
    """
    this needs to be abstract because experimenters also need to access self.ParticipantClass, etc.
    for example, in get_object, it checks if it's self.SubsessionClass
    """

    def persist_classes(self):
        super(InitializeExperimenter, self).persist_classes()
        self.request_session[constants.UserClass] = Experimenter

    def get(self, request, *args, **kwargs):
        self.request_session = {}
        self.initialize_time_limits()

        user_code = self.request.GET[constants.user_code]

        self.user = get_object_or_404(Experimenter, code = user_code)

        self.user.visited = True
        self.user.time_started = django.utils.timezone.now()

        self.user.save()
        self.request_session[constants.user_code] = self.user.code

        self.persist_classes()

        urls = self.user._pages_as_urls()
        if len(urls) > 0:
            url = urls[0]
        else:
            if self.user.subsession._index_in_subsessions == self._session_user._index_in_subsessions:
                self._session_user._index_in_subsessions += 1
                self._session_user.save()
            me_in_next_subsession = self.user.me_in_next_subsession
            if me_in_next_subsession:
                url = me_in_next_subsession._start_url()
            else:
                from ptree.views.concrete import OutOfRangeNotification
                url = OutOfRangeNotification.url(self._session_user)
        return HttpResponseRedirect(url)

class AssignVisitorToOpenSession(vanilla.View):

    def incorrect_parameters_in_url_message(self):
        # A visitor to this experiment was turned away because they did not have the MTurk parameters in their URL.
        # This URL only works if clicked from a MTurk job posting with the JavaScript snippet embedded
        return """To participate, you need to first accept this Mechanical Turk HIT and then re-click the link (refreshing this page will not work)."""

    def url_has_correct_parameters(self):
        for _, get_param_name in self.required_params.items():
            if not self.request.GET.has_key(get_param_name):
                return False
        return True

    def retrieve_existing_participant_with_these_params(self, open_session):
        params = {field_name: self.request.GET[get_param_name] for field_name, get_param_name in self.required_params.items()}
        return SessionParticipant.objects.get(
            session = open_session,
            **params
        )

    def set_external_params_on_participant(self, session_participant):
        for field_name, get_param_name in self.required_params.items():
            setattr(session_participant, field_name, self.request.GET[get_param_name])

    def get(self, *args, **kwargs):
        if not self.request.GET[constants.access_code_for_open_session] == ptree.common.access_code_for_open_session():
            return HttpResponseNotFound('Incorrect access code for open session')

        global_data = ptree.sessionlib.models.GlobalData.objects.get()
        open_session = global_data.open_session

        if not open_session:
            return HttpResponseNotFound('No active session.')
        if not self.url_has_correct_parameters():
            return HttpResponseNotFound(self.incorrect_parameters_in_url_message())
        try:
            session_participant = self.retrieve_existing_participant_with_these_params(open_session)
        except SessionParticipant.DoesNotExist:
            try:
                session_participant = SessionParticipant.objects.filter(
                    session = open_session,
                    visited=False)[0]
                self.set_external_params_on_participant(session_participant)
                session_participant.save()
            except IndexError:
                return HttpResponseNotFound("No Participant objects left in the database to assign to new visitor.")

        return HttpResponseRedirect(session_participant._start_url())

