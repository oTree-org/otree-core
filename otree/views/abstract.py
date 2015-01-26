#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# DOCS
# =============================================================================

"""This module contains many of oTree's internals.

The view classes in this module are just base classes, and cannot be called
from a URL.

You should inherit from these classes and put your view class in your game
directory (under "games/")

Or in the other view file in this directory, which stores shared concrete
views that have URLs.

"""


# =============================================================================
# IMPORTS
# =============================================================================

import os
import logging
import contextlib
import time

from django.db import transaction
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache, cache_control
from django.forms.models import model_to_dict
from django.http import (
    HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
)

import vanilla

import otree.forms
from otree.models.user import Experimenter
from otree.common_internal import get_views_module

import otree.models.session
import otree.timeout.tasks
import otree.models
import otree.models.session as seq_models
import otree.constants as constants
from otree.models.session import Participant, GlobalSingleton
from otree.models_concrete import (
    PageCompletion, WaitPageVisit, CompletedSubsessionWaitPage,
    CompletedGroupWaitPage, SessionuserToUserLookup
)


# Get an instance of a logger
logger = logging.getLogger(__name__)


@contextlib.contextmanager
def no_op_context_manager():
    yield


def get_app_name(request):
    return otree.common_internal.get_app_name_from_import_path(
        request.resolver_match.url_name)


class OTreeMixin(object):
    """Base mixin class for oTree views.

    Takes care of:

        - retrieving model classes and objects automatically,
          so you can access self.group, self.player, etc.

    """

    is_debug = settings.DEBUG
    is_otree_dot_org = 'IS_OTREE_DOT_ORG' in os.environ

    def save_objects(self):
        for obj in self.objects_to_save():
            if obj:
                obj.save()

    @classmethod
    def get_name_in_url(cls):
        # look for name_in_url attribute Constants
        # if it's not part of a game, but rather a shared module etc,
        # SubsessionClass won't exist.
        # in that case, name_in_url needs to be defined on the class.
        if hasattr(cls, 'z_models'):
            return cls.z_models.Constants.name_in_url
        return cls.name_in_url

    def _redirect_to_page_the_user_should_be_on(self):
        """Redirect to where the player should be,
        according to the view index we maintain in the DB
        Useful if the player tried to skip ahead,
        or if they hit the back button.
        We can put them back where they belong.
        """
        return HttpResponseRedirect(self.page_the_user_should_be_on())

    def vars_for_template(self):
        return {}

    def _vars_for_all_templates(self):
        views_module = otree.common_internal.get_views_module(
            self.subsession._meta.app_config.name)
        if hasattr(views_module, 'vars_for_all_templates'):
            return views_module.vars_for_all_templates(self) or {}
        return {}

    def page_the_user_should_be_on(self):
        try:
            return self._session_user._pages_as_urls()[
                self._session_user._index_in_pages
            ]
        except IndexError:
            from otree.views.concrete import OutOfRangeNotification
            return OutOfRangeNotification.url(self._session_user)


class NonSequenceUrlMixin(object):
    @classmethod
    def url(cls, session_user):
        return otree.common_internal.url(cls, session_user)

    @classmethod
    def url_pattern(cls):
        return otree.common_internal.url_pattern(cls, False)


class PlayerMixin(object):

    _is_experimenter = False

    def get_debug_values(self):
        try:
            group_id = self.group.pk
        except:
            group_id = ''
        return [
            ('ID in group', self.player.id_in_group),
            ('Group', group_id),
            ('Player', self.player.pk),
            ('Participant label', self.player.participant.label),
            ('Session code', self.session.code)
        ]

    def get_UserClass(self):
        return self.PlayerClass

    def objects_to_save(self):
        return [self._user, self._session_user,
                self.group, self.subsession.session]


class ExperimenterMixin(object):

    _is_experimenter = True

    def get_debug_values(self):
        return [('Subsession code', self.subsession.code)]

    def get_UserClass(self):
        return Experimenter

    def objects_to_save(self):
        return [
            self._user, self.subsession, self._session_user
        ] + self.subsession.get_players()


class FormPageOrWaitPageMixin(OTreeMixin):
    """
    View that manages its position in the group sequence.
    for both players and experimenters
    """

    @classmethod
    def url(cls, session_user, index):
        return otree.common_internal.url(cls, session_user, index)

    @classmethod
    def url_pattern(cls):
        return otree.common_internal.url_pattern(cls, True)

    def load_objects(self):
        """
        Even though we only use PlayerClass in load_objects,
        we use {Group/Subsession}Class elsewhere.
        """

        # this is the most reliable way to get the app name,
        # because of WaitUntilAssigned...
        user_lookup = SessionuserToUserLookup.objects.get(
            session_user_pk=self._session_user.pk,
            page_index=self._session_user._index_in_pages,
        )

        app_name = user_lookup.app_name
        user_pk = user_lookup.user_pk

        # for the participant changelist
        self._session_user._current_app_name = app_name

        models_module = otree.common_internal.get_models_module(app_name)
        self._models_module = models_module
        self.SubsessionClass = getattr(models_module, 'Subsession')
        self.GroupClass = getattr(models_module, 'Group')
        self.PlayerClass = getattr(models_module, 'Player')
        self.UserClass = self.get_UserClass()

        self._user = get_object_or_404(self.get_UserClass(), pk=user_pk)

        if not self._is_experimenter:
            self.player = self._user
            self.group = self.player.group

        self.subsession = self._user.subsession
        self.session = self._user.session

        # at this point, _session_user already exists, but we reassign this
        # variable
        # the reason is that if we don't do this, there will be
        # self._session_user, and self._user._session_user, which will be 2
        # separate queries, and thus changes made to 1 object will not be
        # reflected in the other.
        self._session_user = self._user._session_user

    @method_decorator(never_cache)
    @method_decorator(cache_control(must_revalidate=True, max_age=0,
                                    no_cache=True, no_store=True))
    def dispatch(self, request, *args, **kwargs):
        try:
            session_user_code = kwargs.pop(constants.session_user_code)
            user_type = kwargs.pop(constants.user_type)
            if user_type == constants.user_type_participant:
                self.SessionUserClass = otree.models.session.Participant
            else:
                self.SessionUserClass = (
                    otree.models.session.SessionExperimenter
                )

            try:
                self._session_user = get_object_or_404(
                    self.SessionUserClass, code=session_user_code
                )
            except Http404 as err:
                msg = (
                    "This user ({}) does not exist in the database. "
                    "Maybe the database was recreated."
                ).format(session_user_code)
                err.message += msg
                raise

            self.load_objects()

            self._index_in_pages = int(kwargs.pop(constants.index_in_pages))

            # if the player tried to skip past a part of the subsession
            # (e.g. by typing in a future URL)
            # or if they hit the back button to a previous subsession
            # in the sequence.
            if not self._user_is_on_right_page():
                cond = (
                    self.request.is_ajax() and
                    self.request.GET.get(constants.check_auto_submit)
                )
                if cond:
                    return HttpResponse('1')
                # then bring them back to where they should be
                return self._redirect_to_page_the_user_should_be_on()

            if not self.participate_condition():
                self._increment_index_in_pages()
                response = self._redirect_to_page_the_user_should_be_on()
            else:
                self._session_user._current_page_name = self.__class__.__name__
                response = super(FormPageOrWaitPageMixin, self).dispatch(
                    request, *args, **kwargs
                )
            self._session_user.last_request_succeeded = True
            self._session_user._last_request_timestamp = time.time()
            self.save_objects()
            return response
        except Exception as e:
            if hasattr(self, '_user'):
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
            e.args = (
                '{}\nDiagnostic info: {}'.format(e.args[0:1], diagnostic_info),
            ) + e.args[1:]
            raise

    # TODO: maybe this isn't necessary, because I can figure out what page
    # they should be on, from looking up index_in_pages
    def _user_is_on_right_page(self):
        """Will detect if a player tried to access a page they didn't reach yet,
        for example if they know the URL to the redemption code page,
        and try typing it in so they don't have to play the whole game.
        We should block that."""

        return self.request.path == self.page_the_user_should_be_on()

    def _increment_index_in_pages(self):
        # when is this not the case?
        assert self._index_in_pages == self._session_user._index_in_pages

        self._record_page_completion_time()
        in_last_page = (
            self._session_user._index_in_pages ==
            self._session_user._max_page_index
        )
        if in_last_page:
            return

        # performance optimization:
        # we skip any page that is a sequence page where participate_condition
        # evaluates to False to eliminate unnecessary redirection
        views_module = get_views_module(self.subsession._meta.app_config.name)
        pages = views_module.pages()

        if self.__class__ in pages:
            pages_to_jump_by = 1
            indexes = range(self._user._index_in_game_pages + 1, len(pages))
            for target_index in indexes:
                Page = pages[target_index]

                # FIXME: are there other attributes? also, not valid for
                # experimenter pages should i do As_view, or simulate the
                # request?
                page = Page()
                page.player = self.player
                page.group = self.group
                page.subsession = self.subsession

                cond = (
                    hasattr(Page, 'participate_condition') and not
                    page.participate_condition()
                )
                if cond:
                    pages_to_jump_by += 1
                else:
                    break

            self._user._index_in_game_pages += pages_to_jump_by
            self._session_user._index_in_pages += pages_to_jump_by
        else:  # e.g. if it's WaitUntil...
            self._session_user._index_in_pages += 1

    def participate_condition(self):
        return True

    def _record_page_completion_time(self):

        now = int(time.time())

        last_page_timestamp = self._session_user._last_page_timestamp
        if last_page_timestamp is None:
            logger.warning(
                'Participant {}: _last_page_timestamp is None'.format(
                    self._session_user.code))
            last_page_timestamp = now

        seconds_on_page = now - last_page_timestamp

        self._session_user._last_page_timestamp = now
        page_name = self.__class__.__name__

        # FIXME: what about experimenter visits?
        completion = PageCompletion(
            app_name=self.subsession.app_name,
            page_index=self._index_in_pages,
            page_name=page_name, time_stamp=now,
            seconds_on_page=seconds_on_page,
            player_pk=self._user.pk,  # FIXME: delete?
            subsession_pk=self.subsession.pk,
            participant_pk=self._session_user.pk,
            session_pk=self.subsession.session.pk,
        )
        completion.save()
        self._session_user.save()


class GenericWaitPageMixin(object):
    """used for in-game wait pages, as well as other wait-type pages oTree has
    (like waiting for session to be created, or waiting for players to be
    assigned to matches

    """

    # TODO: this is intended to be in the user's project, not part of oTree
    # core. But maybe have one in oTree core as a fallback in case the user
    # doesn't have it.
    wait_page_template_name = 'otree/WaitPage.html'

    def title_text(self):
        return 'Please wait'

    def body_text(self):
        return ''

    def request_is_from_wait_page(self):
        check_if_wait_is_over = constants.check_if_wait_is_over
        get_param_tvalue = constants.get_param_truth_value
        return (
            self.request.is_ajax() and
            self.request.GET.get(check_if_wait_is_over) == get_param_tvalue
        )

    def poll_url(self):
        '''called from template'''
        return otree.common_internal.add_params_to_url(
            self.request.path,
            {constants.check_if_wait_is_over: constants.get_param_truth_value}
        )

    def redirect_url(self):
        '''called from template'''
        return self.request.path

    # called from template
    poll_interval_seconds = constants.wait_page_poll_interval_seconds

    def _response_to_wait_page(self):
        return HttpResponse(int(bool(self._is_ready())))

    def _get_wait_page(self):
        response = TemplateResponse(
            self.request,
            self.wait_page_template_name,
            {'view': self}
        )
        response[constants.wait_page_http_header] = (
            constants.get_param_truth_value
        )
        return response

    def _before_returning_wait_page(self):
        pass

    def _response_when_ready(self):
        raise NotImplementedError()

    def dispatch(self, request, *args, **kwargs):
        if self.request_is_from_wait_page():
            return self._response_to_wait_page()
        else:
            if self._is_ready():
                return self._response_when_ready()
            self._before_returning_wait_page()
            return self._get_wait_page()


class InGameWaitPageMixin(object):
    """Wait pages during game play (i.e. checkpoints),
    where users wait for others to complete

    """

    def dispatch(self, request, *args, **kwargs):
        '''this is actually for sequence pages only, because of
        the _redirect_to_page_the_user_should_be_on()

        '''
        if self.wait_for_all_groups:
            self._group_or_subsession = self.subsession
        else:
            self._group_or_subsession = self.group
        if self.request_is_from_wait_page():
            unvisited_ids = self._get_unvisited_ids()
            self._record_unvisited_ids(unvisited_ids)
            return self._response_to_wait_page()
        else:
            if self._is_ready():
                return self._response_when_ready()
            self._session_user.is_on_wait_page = True
            self._record_visit()
            unvisited_ids = self._get_unvisited_ids()
            self._record_unvisited_ids(unvisited_ids)
            if len(unvisited_ids) == 0:

                # on SQLite, transaction.atomic causes database to lock,
                # so we use no-op context manager instead
                if settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
                    context_manager = no_op_context_manager
                else:
                    context_manager = transaction.atomic
                with context_manager():
                    # take a lock on this singleton, so that only 1 person can
                    # be completing a wait page action at a time to avoid race
                    # conditions
                    GlobalSingleton.objects.select_for_update().get()

                    if self.wait_for_all_groups:
                        _c = CompletedSubsessionWaitPage.objects.get_or_create(
                            page_index=self._index_in_pages,
                            session_pk=self.session.pk
                        )
                        _, created = _c
                    else:
                        _c = CompletedGroupWaitPage.objects.get_or_create(
                            page_index=self._index_in_pages,
                            group_pk=self.group.pk,
                            session_pk=self.session.pk
                        )
                        _, created = _c

                    # run the action inside the context manager, so that the
                    # action is completed before the next thread does a
                    # get_or_create and sees that the action has been completed
                    if created:
                        self._action()

                        # in case there is a timeout on the next page, we
                        # should ensure the next pages are visited promptly
                        # TODO: can we make this run only if next page is a
                        # timeout page?
                        # we could instead make this request the current page
                        # URL, but it's different for each player
                        otree.timeout.tasks.ensure_pages_visited.apply_async(
                            kwargs={
                                'app_name': self.subsession.app_name,
                                'participant_pk_set':
                                    self._ids_for_this_wait_page(),
                                'wait_page_index': self._index_in_pages,
                            },
                            countdown=10,
                        )
                        return self._response_when_ready()
            return self._get_wait_page()

    def _is_ready(self):
        """all participants visited, AND action has been run"""
        if self.wait_for_all_groups:
            return CompletedSubsessionWaitPage.objects.filter(
                page_index=self._index_in_pages,
                session_pk=self.session.pk
            ).exists()
        else:
            return CompletedGroupWaitPage.objects.filter(
                page_index=self._index_in_pages,
                group_pk=self.group.pk,
                session_pk=self.session.pk
            ).exists()

    def _ids_for_this_wait_page(self):
        return set([
            p.participant.id_in_session
            for p in self._group_or_subsession.player_set.all()
        ])

    def _get_unvisited_ids(self):
        """side effect: set _waiting_for_ids"""
        visited_ids = set(
            WaitPageVisit.objects.filter(
                session_pk=self.session.pk,
                page_index=self._index_in_pages,
            ).values_list('id_in_session', flat=True)
        )
        ids_for_this_wait_page = self._ids_for_this_wait_page()

        return ids_for_this_wait_page - visited_ids

    def _record_unvisited_ids(self, unvisited_ids):
        # only bother numerating if there are just a few, otherwise it's
        # distracting
        if len(unvisited_ids) <= 3:
            self._session_user._waiting_for_ids = ', '.join(
                'P{}'.format(id_in_session)
                for id_in_session in unvisited_ids)

    def _record_visit(self):
        """record that this player visited"""
        visit, _ = WaitPageVisit.objects.get_or_create(
            session_pk=self.session.pk,
            page_index=self._index_in_pages,

            # FIXME: what about experimenter?
            id_in_session=self._session_user.id_in_session
        )

    def _action(self):
        # force to refresh from DB
        otree.common_internal.get_players(
            self._group_or_subsession, refresh_from_db=True
        )
        self.after_all_players_arrive()
        for p in self._group_or_subsession.get_players():
            p.save()
        self._group_or_subsession.save()

    def participate_condition(self):
        return True

    def _response_when_ready(self):
        self._session_user.is_on_wait_page = False
        self._increment_index_in_pages()
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


class FormPageMixin(object):
    """mixin rather than subclass because we want these methods only to be
    first in MRO

    """

    # if a model is not specified, use empty "StubModel"
    model = otree.models.session.StubModel
    fields = []

    def get_form_class(self):
        form_class = otree.forms.modelform_factory(
            self.form_model, fields=self.form_fields,
            form=otree.forms.ModelForm,
            formfield_callback=otree.forms.formfield_callback
        )
        return form_class

    def after_next_button(self):
        pass

    def get_context_data(self, **kwargs):
        context = super(FormPageMixin, self).get_context_data(**kwargs)
        context.update({
            'form': kwargs.get('form'),
            'player': self.player,
            'group': self.group,
            'subsession': self.subsession,
            'Constants': self._models_module.Constants,
        })
        context.update(self._vars_for_all_templates() or {})
        context.update(self.vars_for_template() or {})
        return context

    def get_form(self, data=None, files=None, **kwargs):
        """Given `data` and `files` QueryDicts, and optionally other named
        arguments, and returns a form.

        """
        cls = self.get_form_class()
        return cls(data=data, files=files, **kwargs)

    def form_invalid(self, form):
        response = super(FormPageMixin, self).form_invalid(form)
        response[constants.redisplay_with_errors_http_header] = (
            constants.get_param_truth_value
        )
        return response

    def get(self, request, *args, **kwargs):
        self._session_user._current_form_page_url = self.request.path
        otree.timeout.tasks.submit_expired_url.apply_async(
            (self.request.path,),
            countdown=self.timeout_seconds
        )
        return super(FormPageMixin, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):

        self.object = self.get_object()

        if request.POST.get(constants.auto_submit):
            self._set_auto_submit_values()
        else:
            form = self.get_form(
                data=request.POST, files=request.FILES, instance=self.object
            )
            if form.is_valid():
                self.form = form
                self.object = form.save()
            else:
                return self.form_invalid(form)
        self.after_next_button()
        self._increment_index_in_pages()
        return self._redirect_to_page_the_user_should_be_on()

    def poll_url(self):
        '''called from template. can't start with underscore because used
        in template

        '''
        return otree.common_internal.add_params_to_url(
            self.request.path,
            {constants.check_auto_submit: constants.get_param_truth_value}
        )

    def redirect_url(self):
        '''called from template'''
        return self.request.path

    # called from template
    poll_interval_seconds = constants.form_page_poll_interval_seconds

    def _set_auto_submit_values(self):
        for field_name in self.form_fields:
            if field_name in self.auto_submit_values:
                value = self.auto_submit_values[field_name]
            else:
                # get default value for datatype if the user didn't specify
                ModelField = self.form_model._meta.get_field_by_name(
                    field_name
                )[0]
                value = ModelField.auto_submit_default
            setattr(self.object, field_name, value)

    def has_timeout(self):
        return self.timeout_seconds is not None and self.timeout_seconds > 0

    timeout_seconds = None


class PlayerUpdateView(FormPageMixin, FormPageOrWaitPageMixin,
                       PlayerMixin, vanilla.UpdateView):

    def get_object(self):
        Cls = self.form_model
        if Cls == self.GroupClass:
            return self.group
        elif Cls == self.PlayerClass:
            return self.player
        elif Cls == seq_models.StubModel:
            return seq_models.StubModel.objects.all()[0]


class ExperimenterUpdateView(FormPageMixin, FormPageOrWaitPageMixin,
                             ExperimenterMixin, vanilla.UpdateView):

    # 2014-9-14: commenting out as i figure out getting rid of forms.py
    # form_class = ExperimenterStubModelForm

    def get_object(self):
        Cls = self.form_model
        if Cls == self.SubsessionClass:
            return self.subsession
        elif Cls == seq_models.StubModel:
            return seq_models.StubModel.objects.all()[0]


class InGameWaitPage(FormPageOrWaitPageMixin, PlayerMixin, InGameWaitPageMixin,
                     GenericWaitPageMixin, vanilla.UpdateView):
    """public API wait page

    """
    pass


class AssignVisitorToOpenSessionBase(vanilla.View):

    def incorrect_parameters_in_url_message(self):
        return 'Missing or incorrect parameters in URL'

    def url_has_correct_parameters(self):
        for _, get_param_name in self.required_params.items():
            if get_param_name not in self.request.GET:
                return False
        return True

    def retrieve_existing_participant_with_these_params(self, open_session):
        params = {
            field_name: self.request.GET[get_param_name]
            for field_name, get_param_name in self.required_params.items()
        }
        return Participant.objects.get(session=open_session, **params)

    def set_external_params_on_participant(self, participant):
        for field_name, get_param_name in self.required_params.items():
            setattr(participant, field_name, self.request.GET[get_param_name])

    def get(self, *args, **kwargs):
        cond = (
            self.request.GET[constants.access_code_for_open_session] ==
            settings.ACCESS_CODE_FOR_OPEN_SESSION
        )
        if not cond:
            return HttpResponseNotFound(
                'Incorrect access code for open session'
            )

        global_singleton = otree.models.session.GlobalSingleton.objects.get()
        open_session = global_singleton.open_session

        if not open_session:
            return HttpResponseNotFound(
                'No session is currently open. Make sure to create '
                'a session and set is as open.'
            )
        if not self.url_has_correct_parameters():
            return HttpResponseNotFound(
                self.incorrect_parameters_in_url_message()
            )
        try:
            participant = (
                self.retrieve_existing_participant_with_these_params(
                    open_session
                )
            )
        except Participant.DoesNotExist:
            with transaction.atomic():
                # just take a lock on an arbitrary object, to prevent multiple
                # threads from executing this code concurrently
                global_singleton = (
                    otree.models.session.GlobalSingleton.objects
                    .select_for_update().get()
                )
                participant = None
                if open_session.session_type.group_by_arrival_time:
                    participant = open_session._next_participant_to_assign()
                if not participant:
                    try:
                        participant = (
                            Participant.objects.select_for_update().filter(
                                session=open_session,
                                visited=False
                            )
                        )[0]
                    except IndexError:
                        return HttpResponseNotFound(
                            "No Player objects left in the database "
                            "to assign to new visitor."
                        )
                self.set_external_params_on_participant(participant)
                # 2014-10-17: needs to be here even if it's also set in
                # the next view to prevent race conditions
                participant.visited = True
                participant.save()

        return HttpResponseRedirect(participant._start_url())
