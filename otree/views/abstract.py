__doc__ = """This module contains many of oTree's internals.
The view classes in this module are just base classes, and cannot be called from a URL.
You should inherit from these classes and put your view class in your game directory (under "games/")
Or in the other view file in this directory, which stores shared concrete views that have URLs."""
import os.path
from threading import Thread
import time
import logging
from datetime import datetime
from otree.db import models
from otree.forms_internal import BaseModelForm, formfield_callback
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.conf import settings
import extra_views
import vanilla
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache, cache_control
from django.utils.translation import ugettext as _
from django.forms.models import model_to_dict

import otree.constants as constants
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
import floppyforms.__future__.models
import otree.models
from otree.models_concrete import PageVisit, WaitPageVisit, CompletedSubsessionWaitPage, CompletedGroupWaitPage, PageExpirationTime

# Get an instance of a logger
logger = logging.getLogger(__name__)

from django.core.urlresolvers import resolve

def get_app_name(request):
    return otree.common.get_app_name_from_import_path(
        request.resolver_match.url_name)

class OTreeMixin(object):
    """Base mixin class for oTree views.
    Takes care of:
    - retrieving model classes and objects automatically,
    so you can access self.group, self.player, etc.
    """

    def load_classes(self):
        """
        Even though we only use PlayerClass in load_objects,
        we use {Group/Subsession}Class elsewhere.
        """

        app_name = self._session_user._current_app_name
        models_module = otree.common.get_models_module(app_name)
        self.SubsessionClass = models.get_model(app_name, 'Subsession')
        self.GroupClass = models.get_model(app_name, 'Group')
        self.PlayerClass = models.get_model(app_name, 'Player')

    def load_user(self):
        code = self._session_user._current_user_code
        UserClass = self._session_user.vars['UserClass']
        try:
            self._user = get_object_or_404(UserClass, code=code)
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

def load_session_user(dispatch_method):
    def wrapped(self, request, *args, **kwargs):
        session_user_code = kwargs.pop(constants.session_user_code)
        user_type = kwargs.pop(constants.user_type)
        if user_type == constants.user_type_participant:
            SessionUserClass = otree.sessionlib.models.Participant
        else:
            SessionUserClass = otree.sessionlib.models.SessionExperimenter

        self._session_user = get_object_or_404(SessionUserClass, code = session_user_code)
        return dispatch_method(self, request, *args, **kwargs)
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

    def get_UserClass(self):
        return self.PlayerClass

    def load_objects(self):
        self.load_user()
        self.player = self._user
        self.group = self.player.group
        # 2/11/2014: group may be undefined because the player may be at a waiting screen
        # before experimenter assigns to a group


    def objects_to_save(self):
        return [self._user, self._session_user, self.group, self.subsession.session]

class ExperimenterMixin(object):

    def get_UserClass(self):
        return Experimenter

    def load_objects(self):
        self.load_user()

    def objects_to_save(self):
        return [self._user, self.subsession, self._session_user] + self.subsession.get_players() + self.subsession.groups

class WaitPageMixin(object):

    # TODO: this is intended to be in the user's project, not part of oTree core.
    # but maybe have one in oTree core as a fallback in case the user doesn't have it.
    wait_page_template_name = 'otree/WaitPage.html'

    def title_text(self):
        return 'Please wait'

    def body_text(self):
        return

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
        response = TemplateResponse(
            self.request,
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
        if self._scope_is_group():
            self._group_or_subsession = self.group
        else:
            self._group_or_subsession = self.subsession
        if self.request_is_from_wait_page():
            return self._response_to_wait_page()
        else:
            self._record_visit()
            if self._all_players_have_visited():
                #FIXME: this could get run for multiple users
                self._mark_complete()
                self._action()
            if self._is_complete():
                return self._redirect_after_complete()
            return self.get_wait_page()

    def _scope_is_group(self):
        '''returns True for match, False for subsession'''
        if issubclass(self.scope, otree.models.BaseGroup):
            return True
        elif issubclass(self.scope, otree.models.BaseSubsession):
            return False
        raise ValueError('scope must be set to either Group or Subsession')

    def _is_complete(self):
        # check the "passed checkpoints" JSON field
        if self._scope_is_group():
            return CompletedGroupWaitPage.objects.filter(
                app_name = self.subsession.app_name,
                page_index = self.index_in_pages,
                group_pk = self.group.pk
            ).exists()
        else:
            return CompletedSubsessionWaitPage.objects.filter(
                app_name = self.subsession.app_name,
                page_index = self.index_in_pages,
                subsession_pk = self.subsession.pk
            ).exists()

    def _all_players_have_visited(self):
        pks_to_wait_for = [p.pk for p in self._group_or_subsession.get_players()]
        pks_that_have_visited = WaitPageVisit.objects.filter(
            app_name = self.subsession.app_name,
            page_index = self.index_in_pages,
        ).values_list('player_pk', flat=True)

        return set(pks_to_wait_for) <= set(pks_that_have_visited)

    def _record_visit(self):
        """record that this player visited"""
        visit, _ = WaitPageVisit.objects.get_or_create(
            app_name = self.subsession.app_name,
            page_index = self.index_in_pages,
            player_pk = self._user.pk, #FIXME: what about experimenter?
        )
        visit.save()

        if self._all_players_have_visited():
            self._action()

    def _page_request_actions(self):
        run_action_now = self._record_visit()
        if run_action_now:
            self._action()

    def _action(self):
        self.after_all_players_arrive()
        for p in self._group_or_subsession.get_players():
            p.save()
        self._group_or_subsession.save()

    def participate_condition(self):
        return True

    def _redirect_after_complete(self):
        self.update_indexes_in_sequences()
        return self._redirect_to_page_the_user_should_be_on()

    def after_all_players_arrive(self):
        pass

    def body_text(self):
        num_other_players = len(self._group_or_subsession.get_players()) - 1
        if num_other_players > 1:
            return 'Waiting for the other participants.'
        elif num_other_players == 1:
            return 'Waiting for the other participant.'
        elif num_other_players == 0:
            return 'Waiting'

    def _mark_complete(self):
        if self._scope_is_group():
            completion, _ = CompletedGroupWaitPage.objects.get_or_create(
                app_name = self.subsession.app_name,
                page_index = self.index_in_pages,
                group_pk = self.group.pk
            )
            completion.save()
        else:
            completion, _ = CompletedSubsessionWaitPage.objects.get_or_create(
                app_name = self.subsession.app_name,
                page_index = self.index_in_pages,
                subsession_pk = self.subsession.pk
            )
            completion.save()


class SequenceMixin(OTreeMixin):
    """
    View that manages its position in the group sequence.
    for both players and experimenters
    """

    @classmethod
    def url(cls, session_user, index):
        return otree.common.url(cls, session_user, index)

    @classmethod
    def url_pattern(cls):
        return otree.common.url_pattern(cls, True)

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

            e.args = ('{}\nDiagnostic info: {}'.format(e.args[0], diagnostic_info),) + e.args[1:]
            raise



    def post(self, request, *args, **kwargs):
        self.time_limit_was_exceeded = self._get_time_limit_was_exceeded(request.POST)
        return super(SequenceMixin, self).post(request, *args, **kwargs)


    def get_context_data(self, **kwargs):
        context = {'form': kwargs.get('form') or kwargs.get('formset')}
        context.update(self.variables_for_template() or {})
        context.update(self._variables_for_all_templates())
        context.update(self._get_time_limit_context())

        if settings.DEBUG:
            context[constants.debug_values] = self.get_debug_values()

        return context

    def get_form(self, data=None, files=None, **kwargs):
        """
        Given `data` and `files` QueryDicts, and optionally other named
        arguments, and returns a form.
        """
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
            self._record_page_visit_time()
            pages = self._user._pages()
            for target_index in range(self.index_in_pages+1, len(pages)):
                Page = pages[target_index]
                # we skip any page that is a sequence page where participate_condition evaluates to true
                if hasattr(Page, 'participate_condition'):
                    #FIXME: just a prototype. there might be other attributes. also, not valid for experimenter pages
                    page = Page()
                    page.player = self.player
                    page.group = self.group
                    page.subsession = self.subsession
                    if not page.participate_condition():
                        continue
                self._user.index_in_pages = target_index
                return
            # if there are no more pages, go to next subsession
            self.update_index_in_subsessions()

    def form_invalid(self, form):
        response = super(SequenceMixin, self).form_invalid(form)
        response[constants.redisplay_with_errors_http_header] = constants.get_param_truth_value
        return response

    def participate_condition(self):
        return True

    def _record_page_visit_time(self):

        now = django.utils.timezone.now()

        seconds_on_page = int((now - self._session_user._last_page_timestamp).total_seconds())
        self._session_user._last_page_timestamp = now

        app_name = self.subsession.app_name,
        round_number = self.subsession.round_number
        page_name = self.__class__.__name__

        # FIXME: what about experimenter visits?
        visit = PageVisit(
            app_name=self.subsession.app_name,
            page_index=self.index_in_pages,
            page_name=page_name,
            completion_time_stamp = now,
            seconds_on_page = seconds_on_page,
            player_pk = self._user.pk,
            subsession_pk = self.subsession.pk,
            participant_pk = self._session_user.pk,
            session_pk = self.subsession.session.pk,
        )

        visit.save()
        self._session_user.save()

    def time_limit_in_seconds(self):
        return None


    def _get_time_limit_context(self):
        time_limit = self.time_limit_in_seconds()
        if not (time_limit is None or time_limit > 0):
            raise ValueError("Time limit must be None or a positive number.")

        if time_limit is None:
            return {}

        now = int(time.time())
        page_expiration_time_if_start_now = now + time_limit

        expiration_info, created = PageExpirationTime.objects.get_or_create(
            app_name = self.subsession.app_name,
            page_index = self.index_in_pages,
            player_pk = self._user.pk,
            defaults = {'expiration_time': page_expiration_time_if_start_now}
        )
        expiration_info.save()

        page_expiration_time = expiration_info.expiration_time
        remaining_seconds = max(0, page_expiration_time - now)

        minutes_component, seconds_component = divmod(remaining_seconds, 60)

        return {
            constants.time_limit_minutes_component: str(minutes_component),
            constants.time_limit_seconds_component: str(seconds_component).zfill(2),
            constants.time_limit_in_seconds: remaining_seconds,
        }


    def _get_time_limit_was_exceeded(self, POST):
        # TODO: add hidden field to forms
        if POST.get('client_side_time_limit_exceeded'):
           return True

        expiration_info = PageExpirationTime.objects.filter(
            app_name = self.subsession.app_name,
            page_index = self.index_in_pages,
            player_pk = self._user.pk,
        )

        if not expiration_info:
            return False
        # first (and only) result from query set
        expiration_info = expiration_info[0]
        return time.time() > (expiration_info.expiration_time + settings.TIME_LIMIT_LATENCY_ALLOWANCE_SECONDS)




class ModelFormMixin(object):
    """mixin rather than subclass because we want these methods only to be first in MRO"""

    # if a model is not specified, use empty "StubModel"
    model = otree.sessionlib.models.StubModel
    fields = []

    def get_form_class(self):
        form_class = otree.forms_internal.modelform_factory(
            self.form_model, fields=self.form_fields, form=BaseModelForm,
            formfield_callback=formfield_callback)
        return form_class


    def after_valid_form_submission(self):
        """Should be implemented by subclasses as necessary"""
        pass

    def form_valid(self, form):
        self.form = form
        self.object = form.save()
        self.post_processing_on_valid_form(form)
        self.after_valid_form_submission()
        self.update_indexes_in_sequences()
        return self._redirect_to_page_the_user_should_be_on()


class PlayerSequenceMixin(SequenceMixin):
    """for players"""

    def get_debug_values(self):
        try:
            group_id = self.group.pk
        except:
            group_id = ''
        return [('Index among players in group', self.player.id_in_group),
                ('Player', self.player.pk),
                ('Group', group_id),
                ('Participant label', self.player.participant.label),
                ('Session code', self.session.code),]


class ExperimenterSequenceMixin(SequenceMixin):

    def get_debug_values(self):
        return [('Subsession code', self.subsession.code),]


class PlayerUpdateView(ModelFormMixin, PlayerSequenceMixin, PlayerMixin, vanilla.UpdateView):

    def get_object(self):
        Cls = self.form_model
        if Cls == self.GroupClass:
            return self.group
        elif Cls == self.PlayerClass:
            return self.player
        elif Cls == seq_models.StubModel:
            return seq_models.StubModel.objects.all()[0]

class WaitPage(PlayerSequenceMixin, PlayerMixin, CheckpointMixin, WaitPageMixin, vanilla.UpdateView):
    pass


class ExperimenterUpdateView(ModelFormMixin, ExperimenterSequenceMixin, ExperimenterMixin, vanilla.UpdateView):
    # 2014-9-14: commenting out as i figure out getting rid of forms.py
    #form_class = ExperimenterStubModelForm

    def get_object(self):
        Cls = self.form_model
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

    @load_session_user
    def dispatch(self, request, *args, **kwargs):
        self.app_name = get_app_name(request)
        return super(InitializePlayerOrExperimenter, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):

        user_code = self.request.GET.get(constants.user_code)

        UserClass = self.get_UserClass()
        self._user = get_object_or_404(UserClass, code = user_code)
        # self._user is a generic name for self.player
        # they are the same thing, but we use 'user' wherever possible
        # so that the code can be copy pasted to experimenter code

        self._user.visited = True
        self._user.save()

        self._session_user._current_app_name = self.app_name
        self._session_user.vars['UserClass'] = UserClass
        self._session_user._current_user_code = user_code
        self._session_user.save()
        return self.redirect()


class InitializePlayer(InitializePlayerOrExperimenter):
    """
    What if I merged this with WaitUntilAssigned?
    """

    def get_UserClass(self):
        models_module = otree.common.get_models_module(self.app_name)
        return models_module.Player

    def redirect(self):
        return HttpResponseRedirect(self._user._pages_as_urls()[0])


class InitializeExperimenter(InitializePlayerOrExperimenter):
    """
    this needs to be abstract because experimenters also need to access self.PlayerClass, etc.
    for example, in get_object, it checks if it's self.SubsessionClass
    """

    def get_UserClass(self):
        return Experimenter

    def redirect(self):
        urls = self._user._pages_as_urls()
        if len(urls) > 0:
            url = urls[0]
        else:
            if self._user.subsession._index_in_subsessions == self._session_user._index_in_subsessions:
                self._session_user._index_in_subsessions += 1
                self._session_user.save()
            me_in_next_subsession = self._user._me_in_next_subsession
            if me_in_next_subsession:
                url = me_in_next_subsession._start_url()
            else:
                from otree.views.concrete import OutOfRangeNotification
                url = OutOfRangeNotification.url(self._session_user)
        return HttpResponseRedirect(url)

class AssignVisitorToOpenSessionBase(vanilla.View):

    def incorrect_parameters_in_url_message(self):
        return 'Missing or incorrect parameters in URL'

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
        if not self.request.GET[constants.access_code_for_open_session] == settings.ACCESS_CODE_FOR_OPEN_SESSION:
            return HttpResponseNotFound('Incorrect access code for open session')

        global_data = otree.sessionlib.models.GlobalSettings.objects.get()
        open_session = global_data.open_session

        if not open_session:
            return HttpResponseNotFound('No session is currently open. Make sure to create a session and set is as open.')
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

