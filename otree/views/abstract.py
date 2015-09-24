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
import time
import warnings
import collections

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache, cache_control
from django.http import (
    HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound)
from django.utils.translation import ugettext as _

import vanilla

import otree.forms
import otree.common_internal

import otree.models.session
import otree.timeout.tasks
import otree.models
import otree.constants_internal as constants
from otree.models.session import Participant
from otree.models.session import GlobalSingleton
from otree.common_internal import (
    lock_on_this_code_path, get_app_label_from_import_path
)

from otree.models_concrete import (
    PageCompletion, WaitPageVisit, CompletedSubsessionWaitPage,
    CompletedGroupWaitPage, SessionuserToUserLookup,
    PageTimeout, StubModel,
    ParticipantLockModel)


# Get an instance of a logger
logger = logging.getLogger(__name__)

NO_PARTICIPANTS_LEFT_MSG = (
    "No Participant objects left in this session "
    "to assign to new visitor.")


DebugTable = collections.namedtuple('DebugTable', ['title', 'rows'])


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

        # shouldn't return HttpResponseRedirect to an AJAX request
        assert not self.request.is_ajax()
        return HttpResponseRedirect(self._session_user._url_i_should_be_on())


class NonSequenceUrlMixin(object):
    @classmethod
    def url(cls, session_user):
        return otree.common_internal.url(cls, session_user)

    @classmethod
    def url_pattern(cls):
        return otree.common_internal.url_pattern(cls, False)


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

    def _get_debug_tables(self):
        try:
            group_id = self.group.id_in_subsession
        except:
            group_id = ''

        rows = [
            ('ID in group', self.player.id_in_group),
            ('Group', group_id),
            ('Round number', self.subsession.round_number),
            ('Participant', self.player.participant._id_in_session_display()),
            ('Participant label', self.player.participant.label or ''),
            ('Session code', self.session.code)]
        return [DebugTable(title='Basic info', rows=rows)]

    def get_UserClass(self):
        return self.PlayerClass

    def objects_to_save(self):
        objs = [self._user, self._session_user, self.session]
        if self.group:
            objs.append(self.group)
            objs.extend(list(self.group._players))
        objs.extend(list(self.subsession._players))
        objs.extend(list(self.subsession._groups))

        return objs

    def load_objects(self):
        """
        Even though we only use PlayerClass in load_objects,
        we use {Group/Subsession}Class elsewhere.

        2015-05-07: shouldn't this go in oTreeMixin?
        because used by all views, not just sequence
        """

        # this is the most reliable way to get the app name,
        # because of WaitUntilAssigned...
        user_lookup = SessionuserToUserLookup.objects.get(
            session_user_pk=self._session_user.pk,
            page_index=self._session_user._index_in_pages)

        app_name = user_lookup.app_name
        user_pk = user_lookup.user_pk

        # for the participant changelist
        self._session_user._current_app_name = app_name

        models_module = otree.common_internal.get_models_module(app_name)
        self._models_module = models_module
        self.SubsessionClass = getattr(models_module, 'Subsession')
        self.GroupClass = getattr(models_module, 'Group')
        self.PlayerClass = getattr(models_module, 'Player')

        self._user = self.PlayerClass.objects.get(pk=user_pk)

        self.player = self._user
        self.group = self.player.group

        self.subsession = self._user.subsession
        self.session = self._user.session

    @method_decorator(never_cache)
    @method_decorator(cache_control(must_revalidate=True, max_age=0,
                                    no_cache=True, no_store=True))
    def dispatch(self, request, *args, **kwargs):
        try:
            with otree.common_internal.transaction_atomic():

                participant_code = kwargs.pop(constants.session_user_code)

                self._index_in_pages = int(
                    kwargs.pop(constants.index_in_pages))

                cond = (
                    self.request.is_ajax() and
                    self.request.GET.get(constants.check_auto_submit))

                # take a lock so that this same code path is not run twice
                # for the same participant
                ParticipantLockModel.objects.select_for_update().get(
                    participant_code=participant_code)

                try:
                    self._session_user = Participant.objects.get(
                        code=participant_code)
                except Participant.DoesNotExist:
                    msg = (
                        "This user ({}) does not exist in the database. "
                        "Maybe the database was recreated."
                    ).format(participant_code)
                    raise Http404(msg)

                if cond:
                    if self._user_is_on_right_page():
                        return HttpResponse('0')
                    return HttpResponse('1')

                # if the player tried to skip past a part of the subsession
                # (e.g. by typing in a future URL)
                # or if they hit the back button to a previous subsession
                # in the sequence.
                #
                if (not self.request.is_ajax()
                        and not self._user_is_on_right_page()):
                    # then bring them back to where they should be
                    return self._redirect_to_page_the_user_should_be_on()

                self.load_objects()

                self._session_user._current_page_name = self.__class__.__name__
                response = super(FormPageOrWaitPageMixin, self).dispatch(
                    request, *args, **kwargs)
                self._session_user.last_request_succeeded = True
                self._session_user._last_request_timestamp = time.time()

                # need to render the response before saving objects,
                # because the template might call a method that modifies
                # player/group/etc.
                if hasattr(response, 'render'):
                    response.render()
                self.save_objects()
                return response
        except Exception:
            if hasattr(self, '_session_user'):
                self._session_user.last_request_succeeded = False
                self._session_user.save()
            raise

    # TODO: maybe this isn't necessary, because I can figure out what page
    # they should be on, from looking up index_in_pages
    def _user_is_on_right_page(self):
        """Will detect if a player tried to access a page they didn't reach
        yet, for example if they know the URL to the redemption code page,
        and try typing it in so they don't have to play the whole game.
        We should block that."""

        return self.request.path == self._session_user._url_i_should_be_on()

    def _increment_index_in_pages(self):
        # when is this not the case?
        assert self._index_in_pages == self._session_user._index_in_pages

        self._record_page_completion_time()
        # we should allow a user to move beyond the last page if it's mturk
        # also in general maybe we should show the 'out of sequence' page

        # the timeout record is irrelevant at this point, delete it
        # wait pages don't have a has_timeout attribute
        if hasattr(self, 'has_timeout') and self.has_timeout():
            PageTimeout.objects.filter(
                participant_pk=self._session_user.pk,
                page_index=self._session_user._index_in_pages).delete()

        # performance optimization:
        # we skip any page that is a sequence page where is_displayed
        # evaluates to False to eliminate unnecessary redirection
        views_module = otree.common_internal.get_views_module(
            self.subsession._meta.app_config.name
        )
        pages = views_module.page_sequence

        if self.__class__ in pages:
            pages_to_jump_by = 1
            indexes = range(self._user._index_in_game_pages + 1, len(pages))
            for target_index in indexes:
                Page = pages[target_index]

                # FIXME: are there other attributes? should i do As_view,
                # or simulate the
                # request?
                page = Page()
                page.player = self.player
                page.group = self.group
                page.subsession = self.subsession

                # don't skip wait pages
                # because the user has to pass through them
                # so we record that they visited
                cond = (
                    hasattr(Page, 'is_displayed') and not
                    hasattr(Page, '_wait_page_flag') and not
                    page.is_displayed())
                if cond:
                    pages_to_jump_by += 1
                else:
                    break

            self._user._index_in_game_pages += pages_to_jump_by
            self._session_user._index_in_pages += pages_to_jump_by
        else:  # e.g. if it's WaitUntil...
            self._session_user._index_in_pages += 1

    def is_displayed(self):
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
            app_name=self.subsession._meta.app_config.name,
            page_index=self._index_in_pages,
            page_name=page_name, time_stamp=now,
            seconds_on_page=seconds_on_page,
            player_pk=self._user.pk,  # FIXME: delete?
            subsession_pk=self.subsession.pk,
            participant_pk=self._session_user.pk,
            session_pk=self.subsession.session.pk)
        completion.save()
        self._session_user.save()


class GenericWaitPageMixin(object):
    """used for in-game wait pages, as well as other wait-type pages oTree has
    (like waiting for session to be created, or waiting for players to be
    assigned to matches

    """

    # for duck typing, indicates this is a wait page
    _wait_page_flag = True

    # TODO: this is intended to be in the user's project, not part of oTree
    # core. But maybe have one in oTree core as a fallback in case the user
    # doesn't have it.
    wait_page_template_name = 'otree/WaitPage.html'

    def title_text(self):
        # Translators: the default title of a wait page
        return _('Please wait')

    def body_text(self):
        return ''

    def request_is_from_wait_page(self):
        check_if_wait_is_over = constants.check_if_wait_is_over
        get_param_tvalue = constants.get_param_truth_value
        return (
            self.request.is_ajax() and
            self.request.GET.get(check_if_wait_is_over) == get_param_tvalue)

    def poll_url(self):
        '''called from template'''
        return otree.common_internal.add_params_to_url(
            self.request.path,
            {constants.check_if_wait_is_over: constants.get_param_truth_value})

    def redirect_url(self):
        '''called from template'''
        return self.request.path

    # called from template
    poll_interval_seconds = constants.wait_page_poll_interval_seconds

    def _response_to_wait_page(self):
        return HttpResponse(int(bool(self._is_ready())))

    def _get_wait_page(self):
        if settings.DEBUG:
            self.debug_tables = self._get_debug_tables()
        response = TemplateResponse(
            self.request, self.wait_page_template_name, {'view': self})
        response[constants.wait_page_http_header] = (
            constants.get_param_truth_value)
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
            if not self.is_displayed():
                self._increment_index_in_pages()
                return self._redirect_to_page_the_user_should_be_on()
            unvisited_ids = self._get_unvisited_ids()
            self._record_unvisited_ids(unvisited_ids)
            if len(unvisited_ids) == 0:

                # on SQLite, transaction.atomic causes database to lock,
                # so we use no-op context manager instead
                with lock_on_this_code_path():
                    if self.wait_for_all_groups:
                        _c = CompletedSubsessionWaitPage.objects.get_or_create(
                            page_index=self._index_in_pages,
                            session_pk=self.session.pk)
                        _, created = _c
                    else:
                        _c = CompletedGroupWaitPage.objects.get_or_create(
                            page_index=self._index_in_pages,
                            group_pk=self.group.pk,
                            session_pk=self.session.pk)
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

                        # 2015-07-27:
                        #   why not check if the next page has_timeout?

                        participant_pk_set = set([
                            p.participant.pk
                            for p in self._group_or_subsession.player_set.all()
                        ])

                        otree.timeout.tasks.ensure_pages_visited.apply_async(
                            kwargs={
                                'participant_pk_set': participant_pk_set,
                                'wait_page_index': self._index_in_pages,
                            }, countdown=10)
                        return self._response_when_ready()
            return self._get_wait_page()

    def _is_ready(self):
        """all participants visited, AND action has been run"""
        if self.wait_for_all_groups:
            return CompletedSubsessionWaitPage.objects.filter(
                page_index=self._index_in_pages,
                session_pk=self.session.pk).exists()
        else:
            return CompletedGroupWaitPage.objects.filter(
                page_index=self._index_in_pages,
                group_pk=self.group.pk,
                session_pk=self.session.pk).exists()

    def _ids_for_this_wait_page(self):
        return set([
            p.participant.id_in_session
            for p in self._group_or_subsession.player_set.all()])

    def _get_unvisited_ids(self):
        """side effect: set _waiting_for_ids"""
        visited_ids = set(
            WaitPageVisit.objects.filter(
                session_pk=self.session.pk,
                page_index=self._index_in_pages,
            ).values_list('id_in_session', flat=True))
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
            id_in_session=self._session_user.id_in_session)

    def _action(self):
        # force to refresh from DB
        self._group_or_subsession._get_players(refresh_from_db=True)
        self.after_all_players_arrive()
        for p in self._group_or_subsession.get_players():
            p.save()
        self._group_or_subsession.save()

    def is_displayed(self):
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
            return _('Waiting for the other participants.')
        elif num_other_players == 1:
            return _('Waiting for the other participant.')
        elif num_other_players == 0:
            # Translators: the default body text on the waiting page
            # to inform the user we are waiting.
            return _('Waiting')


class FormPageMixin(object):
    """mixin rather than subclass because we want these methods only to be
    first in MRO

    """

    # if a model is not specified, use empty "StubModel"
    model = StubModel
    fields = []

    def get_template_names(self):
        if self.template_name is not None:
            template_name = self.template_name
        else:
            template_name = '{}/{}.html'.format(
                get_app_label_from_import_path(self.__module__),
                self.__class__.__name__)
        return [template_name]

    def get_form_fields(self):
        return self.form_fields

    def get_form_class(self):
        fields = self.get_form_fields()
        if self.form_model is StubModel and fields:
            raise Exception(
                'Page "{}" defined form_fields but not form_model'.format(
                    self.__class__.__name__
                )
            )
        form_class = otree.forms.modelform_factory(
            self.form_model, fields=fields,
            form=otree.forms.ModelForm,
            formfield_callback=otree.forms.formfield_callback)
        return form_class

    def before_next_page(self):
        pass

    def get_context_data(self, **kwargs):
        context = super(FormPageMixin, self).get_context_data(**kwargs)
        context.update({
            'form': kwargs.get('form'),
            'player': self.player,
            'group': self.group,
            'subsession': self.subsession,
            'Constants': self._models_module.Constants})
        vars_for_template = self.resolve_vars_for_template()
        context.update(vars_for_template)
        self._vars_for_template = vars_for_template
        if settings.DEBUG:
            self.debug_tables = self._get_debug_tables()
        return context

    def get_form(self, data=None, files=None, **kwargs):
        """Given `data` and `files` QueryDicts, and optionally other named
        arguments, and returns a form.

        """
        cls = self.get_form_class()
        return cls(data=data, files=files, view=self, **kwargs)

    def vars_for_template(self):
        return {}

    def resolve_vars_for_template(self):
        """Resolve all vars for template including "vars_for_all_templates"

        """
        context = {}
        views_module = otree.common_internal.get_views_module(
            self.subsession._meta.app_config.name)
        if hasattr(views_module, 'vars_for_all_templates'):
            context.update(views_module.vars_for_all_templates(self) or {})
        context.update(self.vars_for_template() or {})
        return context

    def form_invalid(self, form):
        response = super(FormPageMixin, self).form_invalid(form)
        response[constants.redisplay_with_errors_http_header] = (
            constants.get_param_truth_value)
        return response

    def get(self, request, *args, **kwargs):
        if not self.is_displayed():
            self._increment_index_in_pages()
            return self._redirect_to_page_the_user_should_be_on()

        self._session_user._current_form_page_url = self.request.path
        if self.has_timeout():
            otree.timeout.tasks.submit_expired_url.apply_async(
                (self.request.path,), countdown=self.timeout_seconds)
        return super(FormPageMixin, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):

        self.object = self.get_object()

        if request.POST.get(constants.auto_submit):
            self.timeout_happened = True  # for public API
            self._set_auto_submit_values()
        else:
            self.timeout_happened = False
            form = self.get_form(
                data=request.POST, files=request.FILES, instance=self.object)
            if form.is_valid():
                self.form = form
                self.object = form.save()
            else:
                return self.form_invalid(form)
        self.before_next_page()
        self._increment_index_in_pages()
        return self._redirect_to_page_the_user_should_be_on()

    def poll_url(self):
        '''called from template. can't start with underscore because used
        in template

        '''
        return otree.common_internal.add_params_to_url(
            self.request.path,
            {constants.check_auto_submit: constants.get_param_truth_value})

    def redirect_url(self):
        '''called from template'''
        return self.request.path

    # called from template
    poll_interval_seconds = constants.form_page_poll_interval_seconds

    def _set_auto_submit_values(self):
        # TODO: auto_submit_values deprecated on 2015-05-28
        auto_submit_values = getattr(self, 'auto_submit_values', {})
        timeout_submission = self.timeout_submission or auto_submit_values
        for field_name in self.form_fields:
            if field_name in timeout_submission:
                value = timeout_submission[field_name]
            else:
                # get default value for datatype if the user didn't specify
                ModelField = self.form_model._meta.get_field_by_name(
                    field_name
                )[0]
                # TODO: should we warn if the attribute doesn't exist?
                value = getattr(ModelField, 'auto_submit_default', None)
            setattr(self.object, field_name, value)

    def has_timeout(self):
        return self.timeout_seconds is not None and self.timeout_seconds > 0

    def remaining_timeout_seconds(self):
        if not self.has_timeout():
            return
        current_time = int(time.time())
        expiration_time = current_time + self.timeout_seconds
        timeout, created = PageTimeout.objects.get_or_create(
            participant_pk=self._session_user.pk,
            page_index=self._session_user._index_in_pages,
            defaults={'expiration_time': expiration_time})

        return timeout.expiration_time - current_time

    timeout_seconds = None

    def _get_debug_tables(self):
        super_tables = super(FormPageMixin, self)._get_debug_tables()
        new_tables = []
        if self._vars_for_template:
            rows = sorted(self._vars_for_template.items())
            new_tables.append(
                DebugTable(title='vars_for_template', rows=rows),)
        return super_tables + new_tables


class PlayerUpdateView(FormPageMixin, FormPageOrWaitPageMixin,
                       vanilla.UpdateView):

    def get_object(self):
        Cls = self.form_model
        if Cls == self.GroupClass:
            return self.group
        elif Cls == self.PlayerClass:
            return self.player
        elif Cls == StubModel:
            return StubModel.objects.all()[0]


class InGameWaitPage(FormPageOrWaitPageMixin, InGameWaitPageMixin,
                     GenericWaitPageMixin, vanilla.UpdateView):
    """public API wait page

    """
    pass


class AssignVisitorToDefaultSessionBase(vanilla.View):
    # TODO: merge this with AssignVisitorToDefaultSession.
    # we used to have the MTurk version but it has been removed.

    def incorrect_parameters_in_url_message(self):
        return 'Missing or incorrect parameters in URL'

    def url_has_correct_parameters(self):
        for i, get_param_name in self.required_params.items():
            if get_param_name not in self.request.GET:
                return False
        return True

    def retrieve_existing_participant_with_these_params(self, default_session):
        params = {
            field_name: self.request.GET[get_param_name]
            for field_name, get_param_name in self.required_params.items()}
        return Participant.objects.get(session=default_session, **params)

    def set_external_params_on_participant(self, participant):
        for field_name, get_param_name in self.required_params.items():
            setattr(participant, field_name, self.request.GET[get_param_name])

    def get(self, *args, **kwargs):
        cond = (
            self.request.GET[constants.access_code_for_default_session] ==
            settings.ACCESS_CODE_FOR_DEFAULT_SESSION)
        if not cond:
            return HttpResponseNotFound(
                'Incorrect access code for default session'
            )

        global_singleton = GlobalSingleton.objects.get()
        default_session = global_singleton.default_session

        if not default_session:
            return HttpResponseNotFound(
                'No session is currently open. Make sure to create '
                'a session and set is as default.'
            )
        if not self.url_has_correct_parameters():
            return HttpResponseNotFound(
                self.incorrect_parameters_in_url_message()
            )
        try:
            participant = (
                self.retrieve_existing_participant_with_these_params(
                    default_session))
        except Participant.DoesNotExist:
            with lock_on_this_code_path():
                try:
                    participant = (
                        Participant.objects.select_for_update().filter(
                            session=default_session,
                            visited=False)).order_by('start_order')[0]
                except IndexError:
                    return HttpResponseNotFound(NO_PARTICIPANTS_LEFT_MSG)

            self.set_external_params_on_participant(participant)
            # 2014-10-17: needs to be here even if it's also set in
            # the next view to prevent race conditions
            participant.visited = True
            participant.save()

        return HttpResponseRedirect(participant._start_url())


class GetFloppyFormClassMixin(object):
    def get_form_class(self):
        """
        A drop-in replacement for
        ``vanilla.model_views.GenericModelView.get_form_class``. The only
        difference is that we use oTree's modelform_factory in order to always
        get a floppyfied form back which supports richer widgets.
        """
        if self.form_class is not None:
            return self.form_class

        if self.model is not None:
            if self.fields is None:
                msg = (
                    "'Using GenericModelView (base class of {}) without "
                    "setting either 'form_class' or the 'fields' attribute "
                    "is pending deprecation.").format(self.__class__.__name__)
                warnings.warn(msg, PendingDeprecationWarning)
            return otree.forms.modelform_factory(
                self.model,
                fields=self.fields,
                formfield_callback=otree.forms.formfield_callback)
        msg = (
            "'{}' must either define 'form_class' or both 'model' and "
            "'fields', or override 'get_form_class()'"
        ).format(self.__class__.__name__)
        raise ImproperlyConfigured(msg)


class AdminSessionPageMixin(GetFloppyFormClassMixin):

    @classmethod
    def url_pattern(cls):
        return r"^{}/(?P<pk>\d+)/$".format(cls.__name__)

    @classmethod
    def url(cls, session_pk):
        return '/{}/{}/'.format(cls.__name__, session_pk)

    def get_context_data(self, **kwargs):
        context = super(AdminSessionPageMixin, self).get_context_data(**kwargs)
        global_singleton = GlobalSingleton.objects.get()
        default_session = global_singleton.default_session
        context.update({
            'session': self.session,
            'is_debug': settings.DEBUG,
            'default_session': default_session})
        return context

    def get_template_names(self):
        return ['otree/admin/{}.html'.format(self.__class__.__name__)]

    def dispatch(self, request, *args, **kwargs):
        session_pk = int(kwargs['pk'])
        self.session = get_object_or_404(otree.models.Session, pk=session_pk)
        return super(AdminSessionPageMixin, self).dispatch(
            request, *args, **kwargs)
