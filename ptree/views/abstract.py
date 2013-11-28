__doc__ = """This module contains many of pTree's internals.
The view classes in this module are just base classes, and cannot be called from a URL.
You should inherit from these classes and put your view class in your game directory (under "games/")
Or in the other view file in this directory, which stores shared concrete views that have URLs."""

from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.core.context_processors import csrf
from django.conf import settings
import extra_views
import vanilla
import time
import ptree.constants as constants
import logging
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache, cache_control
from ptree.forms import StubModelForm
from ptree.sequence_of_experiments.models import StubModel
import urllib
import urlparse


# Get an instance of a logger
logger = logging.getLogger(__name__)

REDIRECT_TO_PAGE_USER_SHOULD_BE_ON_URL = '/shared/RedirectToPageUserShouldBeOn/'

class PTreeMixin(object):
    """Base mixin class for pTree views.
    Takes care of:
    - retrieving model classes and objects automatically,
    so you can access self.treatment, self.match, self.participant, etc.
    """

    def load_classes(self):
        self.ExperimentClass = self.request.session.get(constants.ExperimentClass)
        self.TreatmentClass = self.request.session.get(constants.TreatmentClass)
        self.ParticipantClass = self.request.session.get(constants.ParticipantClass)
        self.MatchClass = self.request.session.get(constants.MatchClass)

    def load_objects(self):
        self.participant = get_object_or_404(self.ParticipantClass,
            code = self.request.session.get(constants.participant_code))
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
        return super(PTreeMixin, self).dispatch(request, *args, **kwargs)

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
        if self.participant.index_in_sequence_of_views >= len(self.treatment.sequence_as_urls()):
            if self.experiment.next_experiment:
                url = self.experiment.next_experiment.start_url(in_sequence_of_experiments = True)

                # add external_id to URL
                if not self.participant.external_id:
                    self.participant.external_id = self.participant.code
                    self.participant.save()
                params_to_add = {constants.external_id: self.participant.external_id}
                url_parts = list(urlparse.urlparse(url))
                query = dict(urlparse.parse_qsl(url_parts[4]))
                query.update(params_to_add)
                url_parts[4] = urllib.urlencode(query)

                return urlparse.urlunparse(url_parts)

        return self.treatment.sequence_as_urls()[self.participant.index_in_sequence_of_views]

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


class SequenceMixin(PTreeMixin):
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

    class PageActions:
        show = 'show'
        skip = 'skip'
        wait = 'wait'

    def show_skip_wait(self):
        return self.PageActions.show

    # TODO: this is intended to be in the user's project, not part of pTree core.
    # but maybe have one in pTree core as a fallback in case the user doesn't have it.
    wait_page_template = 'ptree/WaitPage.html'

    def wait_message(self):
        pass

    def time_limit_seconds(self):
        return None

    def set_time_limit(self, context):
        page_expiration_times = self.request.session[constants.page_time_limits]
        if page_expiration_times.has_key(self.index_in_sequence_of_views):
            page_expiration_time = page_expiration_times[self.index_in_sequence_of_views]
            if page_expiration_time is None:
                remaining_seconds = None
            else:
                remaining_seconds = max(0, int(page_expiration_times[self.index_in_sequence_of_views] - time.time()))
        else:
            remaining_seconds = self.time_limit_seconds()

            if remaining_seconds is None:
                page_expiration_times[self.index_in_sequence_of_views] = None
            elif remaining_seconds > 0:
                page_expiration_times[self.index_in_sequence_of_views] = time.time() + remaining_seconds
            else:
                raise ValueError("Time limit must be None or a positive number.")

        # TODO: this doesn't seem to have any effect. remove?
        # I had to turn on 'save session on every request' in settings anyway.
        self.request.session.modified = True
        context[constants.time_limit_seconds] = remaining_seconds

    time_limit_was_exceeded = False

    def get_time_limit_was_exceeded(self):
        page_expiration_time = self.request.session[constants.page_time_limits][self.index_in_sequence_of_views]
        if page_expiration_time is None:
            return False
        return time.time() > (page_expiration_time + settings.TIME_LIMIT_GRACE_PERIOD_SECONDS)

    def timer_message(self):
        pass

    @method_decorator(never_cache)
    @method_decorator(cache_control(must_revalidate=True, max_age=0, no_cache=True, no_store = True))
    def dispatch(self, request, *args, **kwargs):
        self.load_classes()
        self.load_objects()
        self.index_in_sequence_of_views = int(args[0])
        # remove it since post() may not be able to accept args.
        args = args[1:]

        ssw = self.show_skip_wait()
        if not ssw in [self.PageActions.show, self.PageActions.skip, self.PageActions.wait]:
            raise ValueError('show_skip_wait() must return one of the following: [self.PageActions.show, self.PageActions.skip, self.PageActions.wait]')

        # should also add GET parameter like check_if_prerequisite_is_satisfied, to be explicit.
        if self.request.is_ajax() and self.request.GET[constants.check_if_wait_is_over] == constants.get_param_truth_value:
            no_more_wait = ssw != self.PageActions.wait
            return HttpResponse(int(no_more_wait))

        # if the participant shouldn't see this view, skip to the next
        if ssw == self.PageActions.skip:
            self.participant.index_in_sequence_of_views += 1
            self.participant.save()
            return self.redirect_to_page_the_user_should_be_on()

        # if the participant tried to skip past a part of the experiment
        # (e.g. by typing in a future URL)
        if not self.user_is_on_right_page():
            # then bring them back to where they should be
            return self.redirect_to_page_the_user_should_be_on()

        if ssw == self.PageActions.wait:
            return render_to_response(self.wait_page_template,
                {'SequenceViewURL': '{}?{}={}'.format(self.request.path,
                                                   constants.check_if_wait_is_over,
                                                   constants.get_param_truth_value),
                'debug_values': self.get_debug_values() if settings.DEBUG else None,
                'wait_message': self.wait_message()})
        return super(SequenceMixin, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.time_limit_was_exceeded = self.get_time_limit_was_exceeded()
        return super(SequenceMixin, self).post(request, *args, **kwargs)

    def variables_for_template(self):
        """
        Should be implemented by subclasses
        Return a dictionary that contains the template context variables (see Django documentation)
        You don't need to include the form here; that is taken care of automatically.
        """

        return {}

    def get_context_data(self, **kwargs):

        context = {'form': kwargs['form']}
        context.update(self.variables_for_template())
        context.update(csrf(self.request))
        context['timer_message'] = self.timer_message()

        if settings.DEBUG:
            context[constants.debug_values] = self.get_debug_values()

        self.set_time_limit(context)
        self.save_objects()
        return context


    def get_debug_values(self):
        try:
            match_id = self.match.pk
        except:
            match_id = ''
        return [('Index among participants in match', self.participant.index_among_participants_in_match),
                ('Participant', self.participant.pk),
                ('Match', match_id),
                ('Treatment', self.treatment.pk),
                ('Experiment code', self.experiment.code),]


    def get_extra_form_kwargs(self):
        return {'participant': self.participant,
               'match': self.match,
               'treatment': self.treatment,
               'experiment': self.experiment,
               'request': self.request,
               'time_limit_was_exceeded': self.time_limit_was_exceeded}

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

    def update_index_in_sequence_of_views(self):
        if self.index_in_sequence_of_views == self.participant.index_in_sequence_of_views:
            self.participant.index_in_sequence_of_views += 1

    def post_processing_on_valid_form(self, form):
        pass

    def form_valid(self, form):
        self.form = form
        self.after_valid_form_submission()
        self.post_processing_on_valid_form(form)
        self.update_index_in_sequence_of_views()
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


class BaseView(PTreeMixin, vanilla.View):
    """
    A basic view that provides no method implementations.
    """
    pass

class TemplateView(PTreeMixin, vanilla.TemplateView):
    """
    A template view.
    """
    pass

class SequenceTemplateView(SequenceMixin, vanilla.TemplateView):
    """
    A sequence template view.
    """
    pass


class UpdateView(SequenceMixin, vanilla.UpdateView):

    # if form_class is not provided, we use an empty form based on StubModel.
    form_class = StubModelForm

    def post_processing_on_valid_form(self, form):
        # form.save will also get called by the super() method, so this is technically redundant.
        # but it means that you don't need to access cleaned_data in after_valid_form_submission,
        # which is a little more user friendly.
        form.save(commit = True)

    def get_object(self):
        Cls = self.model or self.form_class.Meta.model
        if Cls == self.MatchClass:
            return self.match
        elif Cls == self.ParticipantClass:
            return self.participant
        elif Cls == StubModel:
            return StubModel.objects.all()[0]
        else:
            # For AuxiliaryModels
            return Cls.objects.get(object_id=self.participant.id,
                                   content_type=ContentType.objects.get_for_model(self.participant))

class CreateView(SequenceMixin, vanilla.CreateView):
    def post_processing_on_valid_form(self, form):
        instance = form.save(commit=False)
        if hasattr(instance, 'participant'):
            instance.participant = self.participant
        if hasattr(instance, 'match'):
            instance.match = self.match
        instance.save()


class ModelFormSetView(extra_views.ModelFormSetView):
    extra = 0

    def formset_valid(self, formset):
        for form in formset:
            self.after_valid_form_submission()
            self.post_processing_on_valid_form(form)
        self.update_index_in_sequence_of_views()
        self.save_objects()
        return super(ModelFormSetView, self).formset_valid(formset)


class CreateMultipleView(extra_views.ModelFormSetView, CreateView):
    pass

class UpdateMultipleView(extra_views.ModelFormSetView, UpdateView):
    pass

class GetTreatmentOrParticipant(vanilla.View):
    """
    The first View when participants visit a site.
    Doesn't have any UI.
    Just looks up the participant,
    decides what Treatment to randomize them to,
    and redirects to that Treatment.
    """

    def get_next_participant_in_experiment(self):
        try:
            return self.ParticipantClass.objects.filter(experiment=self.experiment,
                                                        has_visited=False)[0]
        except IndexError:
            raise IndexError("No Participant objects left in the database to assign to new visitor.")

    def get(self, request, *args, **kwargs):
        self.request.session.clear()
        self.request.session[constants.page_time_limits] = {}

        participant_code = self.request.GET.get(constants.participant_code)
        treatment_code = self.request.GET.get(constants.treatment_code)
        experiment_code = self.request.GET.get(constants.experiment_code_obfuscated)
        sequence_of_experiments_access_code = self.request.GET.get(constants.sequence_of_experiments_access_code)

        assert participant_code or treatment_code or experiment_code

        self.participant = None
        self.experiment = None
        self.treatment = None

        if experiment_code:
            self.experiment = get_object_or_404(self.ExperimentClass, code = experiment_code)

            if sequence_of_experiments_access_code and sequence_of_experiments_access_code == self.experiment.sequence_of_experiments_access_code:
                self.participant = self.get_next_participant_in_experiment()
            elif self.experiment.sequence_of_experiments.is_for_mturk:
                try:
                    self.assign_participant_with_mturk_parameters()
                except AssertionError:
                    return HttpResponse('To participate, you need to first accept this Mechanical Turk HIT and then re-click the link (refreshing this page will not work).')
            else:
                self.participant = self.get_next_participant_in_experiment()

        if participant_code:
            self.participant = get_object_or_404(self.ParticipantClass, code = participant_code)
            self.experiment = self.participant.experiment

        if self.participant and self.experiment:
            if self.participant.match:
                self.treatment = self.participant.match.treatment
            else:
                self.treatment = self.experiment.pick_treatment_for_incoming_participant()

        elif treatment_code:
            # demo mode
            self.treatment = get_object_or_404(self.TreatmentClass, code=treatment_code)
            self.experiment = self.treatment.experiment
            self.participant = self.get_next_participant_in_experiment()

        external_id = self.request.GET.get(constants.external_id)
        if external_id is not None:
            self.participant.external_id = external_id
        self.participant.has_visited = True
        self.participant.treatment = self.treatment
        self.participant.save()
        self.request.session[constants.participant_code] = self.participant.code
        self.request.session[constants.treatment_code] = self.treatment.code

        return HttpResponseRedirect('/{}/StartTreatment/{}/'.format(self.experiment.url_base, 0))

    def assign_participant_with_mturk_parameters(self):
        try:
            mturk_worker_id = self.request.GET[constants.mturk_worker_id]
            mturk_assignment_id = self.request.GET[constants.mturk_assignment_id]
            assert mturk_assignment_id != 'ASSIGNMENT_ID_NOT_AVAILABLE'
        except:
            print 'A visitor to this experiment was turned away because they did not have the MTurk parameters in their URL.'
            print 'This URL only works if clicked from a MTurk job posting with the JavaScript snippet embedded'
            raise AssertionError()

        try:
            self.participant = self.ParticipantClass.objects.get(experiment=self.experiment,
                                                                 mturk_worker_id = mturk_worker_id)
        except self.ParticipantClass.DoesNotExist:
            self.get_next_participant_in_experiment()
            self.participant.mturk_worker_id = mturk_worker_id
            self.participant.mturk_assignment_id = mturk_assignment_id



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

class StartTreatment(UpdateView):
    """Start page. Each game should have a Start view that inherits from this.
    This is not a modelform, because it can be used with many models.
    """

    def load_classes(self):
        """Don't want to load from cookies"""

    def load_objects(self):
        self.match = None # match not created yet.
        self.participant = get_object_or_404(self.ParticipantClass,
                                             code = self.request.session[constants.participant_code])
        self.treatment = get_object_or_404(self.TreatmentClass,
                                           code = self.request.session[constants.treatment_code])
        self.experiment = self.participant.experiment

    def persist_classes(self):
        """We need these classes so that we can load the objects.
        We need to store it in cookies,
        rather than relying on each View knowing its Experiment, Treatment, etc.
        Although this is the case with the views in the games (which inherit from their Start view),
        some Views are in a shared module and therefore can be bound to different Experiments, Treatments, etc.
        """

        self.request.session[constants.ExperimentClass] = self.ExperimentClass
        self.request.session[constants.TreatmentClass] = self.TreatmentClass
        self.request.session[constants.ParticipantClass] = self.ParticipantClass
        self.request.session[constants.MatchClass] = self.MatchClass

    def variables_for_template(self):
        self.request.session.set_test_cookie()
        self.persist_classes()
        return {}

    def after_valid_form_submission(self):
        if self.participant.ip_address == None:
            self.participant.ip_address = self.request.META['REMOTE_ADDR']

        if self.request.session.test_cookie_worked():
            self.request.session.delete_test_cookie()
        else:
            raise HttpResponse("Your browser does not support this site's cookies.")

        self.configure_match()

    def configure_match(self):
        """
        Find the participant and associate him with an existing or new match.
        """

        if self.participant.match:
            self.match = self.participant.match
        else:
            self.match = self.treatment.next_open_match() or self.create_match()
            self.add_participant_to_match()
            
        assert self.match
        assert self.match.treatment

    def create_match(self):
        match = self.MatchClass(treatment = self.treatment,
                                experiment = self.experiment)
        # need to save it before you assign the participant.match ForeignKey
        match.save()
        return match

    def add_participant_to_match(self):
        self.participant.index_among_participants_in_match = self.match.participant_set.count()
        self.participant.match = self.match