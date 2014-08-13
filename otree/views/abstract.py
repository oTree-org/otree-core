__doc__ = """This module contains many of oTree's internals.
The view classes in this module are just base classes, and cannot be called from a URL.
You should inherit from these classes and put your view class in your game directory (under "games/")
Or in the other view file in this directory, which stores shared concrete views that have URLs."""
import os.path
from threading import Thread
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

import otree.constants as constants
from otree.forms_internal import StubModelForm, ExperimenterStubModelForm
import otree.sessionlib.models as seq_models
import otree.sessionlib.models
import otree.common

import otree.user.models
import otree.forms_internal
from otree.user.models import Experimenter
import copy
import django.utils.timezone

from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
import vanilla
from django.utils.translation import ugettext as _
import otree.sessionlib.models
from otree.sessionlib.models import Participant
from Queue import Queue
import sys
# Get an instance of a logger
logger = logging.getLogger(__name__)

class OTreeMixin(object):
    """Base mixin class for oTree views.
    Takes care of:
    - retrieving model classes and objects automatically,
    so you can access view.treatment, self.match, self.player, etc.
    """

    def load_classes(self):
        """
        Even though we only use PlayerClass in load_objects,
        we use {Match/Treatment/Subsession}Class elsewhere.
        We don't need this as long as people have the correct mixins,
        but it's likely that people will forget to put the mixin.
        """

        self.SubsessionClass = self.request_session.get(constants.SubsessionClass)
        self.TreatmentClass = self.request_session.get(constants.TreatmentClass)
        self.PlayerClass = self.request_session.get(constants.PlayerClass)
        self.MatchClass = self.request_session.get(constants.MatchClass)
        self.UserClass = self.request_session.get(constants.UserClass)

    def load_user(self):
        code = self.request_session[constants.user_code]
        try:
            self._user = get_object_or_404(self.UserClass, code=code)
        except ValueError:
            raise Http404("This user ({}) does not exist in the database. Maybe the database was recreated.".format(code))
        self.subsession = self._user.subsession
        self.session = self._user.session

        # at this point, _session_user already exists, but we reassign this variable
        # the reason is that if we don't do this, there will be self._session_user, and
        # self._user._session_user, which will be 2 separate queries, and thus changes made to 1 object
        # will not be reflected in the other.
        self._session_user = self._user._session_user

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

    def _redirect_to_page_the_user_should_be_on(self):
        """Redirect to where the player should be,
        according to the view index we maintain in the DB
        Useful if the player tried to skip ahead,
        or if they hit the back button.
        We can put them back where they belong.
        """
        return HttpResponseRedirect(self.page_the_user_should_be_on())

    def variables_for_template(self):
        return {}

    def _variables_for_all_templates(self):
        views_module = otree.common._views_module(self.subsession)
        if hasattr(views_module, 'variables_for_all_templates'):
            return views_module.variables_for_all_templates(self) or {}
        return {}

    def get_context_data(self, **kwargs):
        context = {}
        context.update(self.variables_for_template() or {})
        context.update(self._variables_for_all_templates())
        return context

    def page_the_user_should_be_on(self):
        if self._session_user._index_in_subsessions > self.subsession._index_in_subsessions:
            users = self._session_user._users()
            try:
                return users[self._session_user._index_in_subsessions]._start_url()
            except IndexError:
                from otree.views.concrete import OutOfRangeNotification
                return OutOfRangeNotification.url(self._session_user)

        return self._user._pages_as_urls()[self._user.index_in_pages]

    def get_request_session(self):
        return self.request.session[self._session_user.code]

def load_session_user(dispatch_method):
    def wrapped(self, request, *args, **kwargs):
        session_user_code = kwargs.pop(constants.session_user_code)
        user_type = kwargs.pop(constants.user_type)
        if user_type == constants.user_type_participant:
            SessionUserClass = otree.sessionlib.models.Participant
        else:
            SessionUserClass = otree.sessionlib.models.SessionExperimenter

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
        return otree.common.url(cls, session_user)

    @classmethod
    def url_pattern(cls):
        return otree.common.url_pattern(cls, False)

class PlayerMixin(object):

    def load_objects(self):
        self.load_user()
        self.player = self._user
        self.match = self.player.match
        # 2/11/2014: match may be undefined because the player may be at a waiting screen
        # before experimenter assigns to a match & treatment.
        self.treatment = self.player.treatment

    def objects_to_save(self):
        return [self._user, self._session_user, self.match, self.subsession.session]

class ExperimenterMixin(object):

    def load_objects(self):
        self.load_user()

    def objects_to_save(self):
        return [self._user, self.subsession, self._session_user] + self.subsession.players + self.subsession.matches #+ self.subsession.treatments

class WaitPageMixin(object):

    # TODO: this is intended to be in the user's project, not part of oTree core.
    # but maybe have one in oTree core as a fallback in case the user doesn't have it.
    wait_page_template_name = 'otree/WaitPage.html'

    def title_text(self):
        return 'Please wait'

    def body_text(self):
        pass

    def request_is_from_wait_page(self):
        return self.request.is_ajax() and self.request.GET.get(constants.check_if_wait_is_over) == constants.get_param_truth_value

    def wait_page_request_url(self):
        return '{}?{}={}'.format(
            self.request.path,
            constants.check_if_wait_is_over,
            constants.get_param_truth_value
        )

    def get_debug_values(self):
        pass

    def _response_to_wait_page(self):
        return HttpResponse(int(bool(self._is_complete())))

    def get_wait_page(self):
        response = render_to_response(
            self.wait_page_template_name,
            {
                'wait_page_url': self.wait_page_request_url(),
                'debug_values': self.get_debug_values() if settings.DEBUG else None,
                'body_text': self.body_text(),
                'title_text': self.title_text()
            }
        )
        response[constants.wait_page_http_header] = constants.get_param_truth_value
        return response

    def _page_request_actions(self):
        pass

    def _redirect_after_complete(self):
        raise NotImplementedError()

    def dispatch(self, request, *args, **kwargs):
        '''this is actually for sequence pages only, because of the _redirect_to_page_the_user_should_be_on()'''
        if self.request_is_from_wait_page():
            return self._response_to_wait_page()
        else:
            if self._is_complete():
                return self._redirect_after_complete()
            self._page_request_actions()
            return self.get_wait_page()


class CheckpointMixin(object):

    def dispatch(self, request, *args, **kwargs):
        '''this is actually for sequence pages only, because of the _redirect_to_page_the_user_should_be_on()'''
        if self.request_is_from_wait_page():
            return self._response_to_wait_page()
        else:
            self._page_request_actions()
            if self._is_complete():
                return self._redirect_after_complete()
            return self.get_wait_page()


    def _is_complete(self):
        # check the "passed checkpoints" JSON field
        return self._match_or_subsession._checkpoint_is_complete(self.index_in_pages)

    def _record_visit(self):
        """record that this player visited"""
        # lock the match/subsession to avoid race conditions
        self._match_or_subsession_locked = self._match_or_subsession._refresh_with_lock()
        run_action_now = self._match_or_subsession_locked._record_checkpoint_visit(self.index_in_pages, self._user.pk)
        self._match_or_subsession_locked.save()
        return run_action_now

    def _page_request_actions(self):
        run_action_now = self._record_visit()
        if run_action_now:
            self._run_action_in_thread()

    def _run_action_in_thread(self):
        failure_queue = Queue()
        t = Thread(target=self._action, args=(failure_queue,))
        t.start()
        t.join()
        if failure_queue.qsize() > 0:
            exc = failure_queue.get()
            # from 'http://stackoverflow.com/a/1278740'
            exc_type, exc_obj, exc_tb = exc
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            error_message = '{}, {}, {}'.format(exc_type.__name__, fname, exc_tb.tb_lineno)
            raise Exception(error_message)

    def _action(self, failure_queue):
        '''do in a background thread and lock the DB'''
        # don't use the locked one because we need to run the action in the user's code
        # that refers to self.match or self.subsession
        try:
            self.action()
            for p in self.players_in_match_or_subsession():
                p.save()
            # need to mark complete after the action, in case the action fails
            # and the thread throws an exception
            # before action is complete
            self._match_or_subsession._mark_checkpoint_complete(self.index_in_pages)
            self._match_or_subsession.save()
        except:
            failure_queue.put(sys.exc_info())
            raise

    def participate_condition(self):
        return True

    def _redirect_after_complete(self):
        self.update_indexes_in_sequences()
        return self._redirect_to_page_the_user_should_be_on()

    def action(self):
        pass

class MatchCheckpointMixin(CheckpointMixin):

    def dispatch(self, request, *args, **kwargs):
        self._match_or_subsession = self.match
        return super(MatchCheckpointMixin, self).dispatch(request, *args, **kwargs)

    def players_in_match_or_subsession(self):
        return self.match.players

    def body_text(self):
        if self.match.players_per_match == 2:
            return 'Waiting for the other player.'
        if self.match.players_per_match > 2:
            return 'Waiting for other players.'

class SubsessionCheckpointMixin(CheckpointMixin):

    def dispatch(self, request, *args, **kwargs):
        self._match_or_subsession = self.subsession
        return super(SubsessionCheckpointMixin, self).dispatch(request, *args, **kwargs)

    def players_in_match_or_subsession(self):
        return self.subsession.players

    def body_text(self):
        return 'Waiting for other players.'

class SequenceMixin(OTreeMixin):
    """
    View that manages its position in the match sequence.
    for both players and experimenters
    """

    @classmethod
    def url(cls, session_user, index):
        return otree.common.url(cls, session_user, index)

    @classmethod
    def url_pattern(cls):
        return otree.common.url_pattern(cls, True)

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
                return self._redirect_to_page_the_user_should_be_on()

            self.index_in_pages = int(kwargs.pop(constants.index_in_pages))

            # if the player tried to skip past a part of the subsession
            # (e.g. by typing in a future URL)
            # or if they hit the back button to a previous subsession in the sequence.
            if not self._user_is_on_right_page():
                # then bring them back to where they should be
                return self._redirect_to_page_the_user_should_be_on()

            if not self.participate_condition():
                self.update_indexes_in_sequences()
                response = self._redirect_to_page_the_user_should_be_on()
            else:
                self._session_user.current_page = self.__class__.__name__
                # by default it's false (e.g. for GET requests), but can be set to True in post() method
                self.time_limit_was_exceeded = False
                response = super(SequenceMixin, self).dispatch(request, *args, **kwargs)
            self._session_user.last_request_succeeded = True
            self.save_objects()
            return response
        except Exception, e:

            if hasattr(self, 'user'):
                user_info = 'user: {}'.format(model_to_dict(self._user))
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
        context.update(self._variables_for_all_templates())
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

    def _user_is_on_right_page(self):
        """Will detect if a player tried to access a page they didn't reach yet,
        for example if they know the URL to the redemption code page,
        and try typing it in so they don't have to play the whole game.
        We should block that."""

        return self.request.path == self.page_the_user_should_be_on()

    def update_index_in_subsessions(self):
        if self.subsession._index_in_subsessions == self._session_user._index_in_subsessions:
            self._session_user._index_in_subsessions += 1

    def update_indexes_in_sequences(self):
        if self.index_in_pages == self._user.index_in_pages:
            self._user.index_in_pages += 1
            if self._user.index_in_pages >= len(self._user._pages_as_urls()):
                self.update_index_in_subsessions()

    def form_invalid(self, form):
        response = super(SequenceMixin, self).form_invalid(form)
        response[constants.redisplay_with_errors_http_header] = constants.get_param_truth_value
        return response

    def participate_condition(self):
        return True

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


class PlayerSequenceMixin(SequenceMixin):
    """for players"""

    def get_debug_values(self):
        try:
            match_id = self.match.pk
        except:
            match_id = ''
        return [('Index among players in match', self.player.index_among_players_in_match),
                ('Player', self.player.pk),
                ('Match', match_id),
                ('Treatment', self.treatment.pk),
                ('Session code', self.session.code),]


    def get_extra_form_kwargs(self):
        return {'player': self.player,
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



class BaseView(OTreeMixin, NonSequenceUrlMixin, vanilla.View):
    """
    A basic view that provides no method implementations.
    """
    pass



class PlayerUpdateView(ModelFormMixin, PlayerSequenceMixin, PlayerMixin, vanilla.UpdateView):

    # if form_class is not provided, we use an empty form based on StubModel.
    form_class = StubModelForm

    def get_object(self):
        Cls = self.get_form_class().Meta.model
        if Cls == self.MatchClass:
            return self.match
        elif Cls == self.PlayerClass:
            return self.player
        elif Cls == seq_models.StubModel:
            return seq_models.StubModel.objects.all()[0]
        else:
            # For AuxiliaryModels
            return Cls.objects.get(object_id=self.player.id,
                                   content_type=ContentType.objects.get_for_model(self.player))


class MatchCheckpoint(PlayerSequenceMixin, PlayerMixin, MatchCheckpointMixin, WaitPageMixin, vanilla.UpdateView):
    pass

class SubsessionCheckpoint(PlayerSequenceMixin, PlayerMixin, SubsessionCheckpointMixin, WaitPageMixin, vanilla.UpdateView):
    pass


class ExperimenterUpdateView(ModelFormMixin, ExperimenterSequenceMixin, ExperimenterMixin, vanilla.UpdateView):
    form_class = ExperimenterStubModelForm

    def get_object(self):
        Cls = self.get_form_class().Meta.model
        if Cls == self.SubsessionClass:
            return self.subsession
        elif Cls == seq_models.StubModel:
            return seq_models.StubModel.objects.all()[0]


class InitializePlayerOrExperimenter(NonSequenceUrlMixin, vanilla.View):

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
        self.request_session[constants.PlayerClass] = self.z_models.Player
        self.request_session[constants.MatchClass] = self.z_models.Match

    def get_request_session(self):
        return {}

    @load_session_user
    def dispatch(self, request, *args, **kwargs):
        return super(InitializePlayerOrExperimenter, self).dispatch(request, *args, **kwargs)

class InitializePlayer(InitializePlayerOrExperimenter):
    """
    What if I merged this with WaitUntilAssigned?
    """

    def get(self, request, *args, **kwargs):
        self.request_session = {}
        self.initialize_time_limits()

        user_code = self.request.GET.get(constants.user_code)

        self._user = get_object_or_404(self.z_models.Player, code = user_code)
        # self._user is a generic name for self.player
        # they are the same thing, but we use 'user' wherever possible
        # so that the code can be copy pasted to experimenter code
        self.player = self._user
        self.subsession = self.player.subsession

        self._user.visited = True
        self._user.time_started = django.utils.timezone.now()

        self._user.save()
        self.request_session[constants.user_code] = self._user.code

        self.persist_classes()
        return HttpResponseRedirect(self._user._pages_as_urls()[0])

    def get_next_player_in_subsession(self):
        try:
            return self.z_models.Player.objects.filter(
                subsession=self.subsession,
                visited=False)[0]
        except IndexError:
            raise IndexError("No Player objects left in the database to assign to new visitor.")

    def persist_classes(self):
        super(InitializePlayer, self).persist_classes()
        self.request_session[constants.UserClass] = self.z_models.Player

class InitializeExperimenter(InitializePlayerOrExperimenter):
    """
    this needs to be abstract because experimenters also need to access self.PlayerClass, etc.
    for example, in get_object, it checks if it's self.SubsessionClass
    """

    def persist_classes(self):
        super(InitializeExperimenter, self).persist_classes()
        self.request_session[constants.UserClass] = Experimenter

    def get(self, request, *args, **kwargs):
        self.request_session = {}
        self.initialize_time_limits()

        user_code = self.request.GET[constants.user_code]

        self._user = get_object_or_404(Experimenter, code = user_code)

        self._user.visited = True
        self._user.time_started = django.utils.timezone.now()

        self._user.save()
        self.request_session[constants.user_code] = self._user.code

        self.persist_classes()

        urls = self._user._pages_as_urls()
        if len(urls) > 0:
            url = urls[0]
        else:
            if self._user.subsession._index_in_subsessions == self._session_user._index_in_subsessions:
                self._session_user._index_in_subsessions += 1
                self._session_user.save()
            me_in_next_subsession = self._user.me_in_next_subsession
            if me_in_next_subsession:
                url = me_in_next_subsession._start_url()
            else:
                from otree.views.concrete import OutOfRangeNotification
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
        return Participant.objects.get(
            session = open_session,
            **params
        )

    def set_external_params_on_participant(self, participant):
        for field_name, get_param_name in self.required_params.items():
            setattr(participant, field_name, self.request.GET[get_param_name])

    def get(self, *args, **kwargs):
        if not self.request.GET[constants.access_code_for_open_session] == otree.common.access_code_for_open_session():
            return HttpResponseNotFound('Incorrect access code for open session')

        global_data = otree.sessionlib.models.GlobalData.objects.get()
        open_session = global_data.open_session

        if not open_session:
            return HttpResponseNotFound('No active session.')
        if not self.url_has_correct_parameters():
            return HttpResponseNotFound(self.incorrect_parameters_in_url_message())
        try:
            participant = self.retrieve_existing_participant_with_these_params(open_session)
        except Participant.DoesNotExist:
            try:
                participant = Participant.objects.filter(
                    session = open_session,
                    visited=False)[0]
                self.set_external_params_on_participant(participant)
                participant.save()
            except IndexError:
                return HttpResponseNotFound("No Player objects left in the database to assign to new visitor.")

        return HttpResponseRedirect(participant._start_url())

