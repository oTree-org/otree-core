# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTS
# =============================================================================

import os
import logging
import time
import warnings
import collections
import json
import contextlib

import django.db
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache, cache_control
from django.http import HttpResponseRedirect, Http404
from django.utils.translation import ugettext as _
from huey.contrib.djhuey import HUEY
from six.moves import range

import channels
import vanilla

import otree.forms
import otree.common_internal
import otree.models.session
import otree.timeout.tasks
import otree.models
import otree.db.idmap
import otree.constants_internal as constants
from otree.models.participant import Participant
from otree.common_internal import get_app_label_from_import_path

from otree.models_concrete import (
    PageCompletion, CompletedSubsessionWaitPage,
    CompletedGroupWaitPage, PageTimeout, StubModel, ParticipantLockModel,
    BrowserBotSubmit
)
from otree.models.session import GlobalSingleton


# Get an instance of a logger
logger = logging.getLogger(__name__)

NO_PARTICIPANTS_LEFT_MSG = (
    "The maximum number of participants for this session has been exceeded."
)


DebugTable = collections.namedtuple('DebugTable', ['title', 'rows'])


@contextlib.contextmanager
def lock_on_this_code_path(recheck_interval=0.1):
    TIMEOUT = 10
    start_time = time.time()
    while time.time() - start_time < TIMEOUT:
        updated_locks = GlobalSingleton.objects.filter(
            locked=False
        ).update(locked=True)
        if not updated_locks:
            time.sleep(recheck_interval)
        else:
            try:
                yield
            finally:
                GlobalSingleton.objects.update(locked=False)
            return
    raise Exception('Request for global lock is stuck')


@contextlib.contextmanager
def participant_lock(participant_code):
    '''
    prevent the same participant from executing the page twice
    use this instead of a transaction because it's more lightweight.
    transactions make it harder to reason about wait pages
    '''
    TIMEOUT = 10
    start_time = time.time()
    while time.time() - start_time < TIMEOUT:
        updated_locks = ParticipantLockModel.objects.filter(
            participant_code=participant_code,
            locked=False
        ).update(locked=True)
        if not updated_locks:
            time.sleep(0.2)
        else:
            try:
                yield
            finally:
                ParticipantLockModel.objects.filter(
                    participant_code=participant_code,
                ).update(locked=False)
            return
    exists = ParticipantLockModel.objects.filter(
        participant_code=participant_code
    ).exists()
    if not exists:
        raise Http404((
            "This user ({}) does not exist in the database. "
            "Maybe the database was recreated."
        ).format(participant_code))
    raise Exception(
        'Request for participant {} is stuck'.format(participant_code))


class SaveObjectsMixin(object):
    '''maybe doesn't need to be a mixin, but i am keeping it that way
    for now so that the test_views_saveobjectsmixin.py still works'''
    def _get_save_objects_model_instances(self):
        return otree.db.idmap._get_save_objects_model_instances()

    def save_objects(self):
        return otree.db.idmap.save_objects()


class OTreeMixin(SaveObjectsMixin, object):
    """Base mixin class for oTree views.

    Takes care of:

        - retrieving model classes and objects automatically,
          so you can access self.group, self.player, etc.

    """

    is_debug = settings.DEBUG
    is_otree_dot_org = 'IS_OTREE_DOT_ORG' in os.environ

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
        return HttpResponseRedirect(self.participant._url_i_should_be_on())


class NonSequenceUrlMixin(object):
    @classmethod
    def url(cls, participant):
        return otree.common_internal.url(cls, participant)

    @classmethod
    def url_pattern(cls):
        return otree.common_internal.url_pattern(cls, False)


class FormPageOrInGameWaitPageMixin(OTreeMixin):
    """
    View that manages its position in the group sequence.
    for both players and experimenters
    """

    @classmethod
    def url(cls, participant, index):
        return otree.common_internal.url(cls, participant, index)

    @classmethod
    def url_pattern(cls):
        return otree.common_internal.url_pattern(cls, True)

    def get_context_data(self, **kwargs):
        context = super(FormPageOrInGameWaitPageMixin,
                        self).get_context_data(**kwargs)
        context.update({
            'form': kwargs.get('form'),
            'player': self.player,
            'group': self.group,
            'subsession': self.subsession,
            'session': self.session,
            'participant': self.participant,
            'Constants': self._models_module.Constants,
            'use_browser_bots': self.session._use_browser_bots,
        })
        vars_for_template = self.resolve_vars_for_template()
        context.update(vars_for_template)
        self._vars_for_template = vars_for_template
        if settings.DEBUG:
            self.debug_tables = self._get_debug_tables()
        return context

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

    def _get_debug_tables(self):
        try:
            group_id = self.group.id_in_subsession
        except:
            group_id = ''

        basic_info_table = DebugTable(
            title='Basic info',
            rows=[
                ('ID in group', self.player.id_in_group),
                ('Group', group_id),
                ('Round number', self.subsession.round_number),
                ('Participant', self.player.participant._id_in_session()),
                ('Participant label', self.player.participant.label or ''),
                ('Session code', self.session.code)
            ]
        )

        new_tables = [basic_info_table]
        if self._vars_for_template:
            rows = sorted(self._vars_for_template.items())
            title = '<code>vars_for_template()</code>'
            new_tables.append(DebugTable(title=title, rows=rows))

        return new_tables

    def load_objects(self):
        """
        Even though we only use PlayerClass in load_objects,
        we use {Group/Subsession}Class elsewhere.

        2015-05-07: shouldn't this go in oTreeMixin?
        because used by all views, not just sequence
        """

        player_lookup = self.participant.player_lookup()

        app_name = player_lookup.app_name
        player_pk = player_lookup.player_pk

        # for the participant changelist
        self.participant._current_app_name = app_name

        models_module = otree.common_internal.get_models_module(app_name)
        self._models_module = models_module
        self.SubsessionClass = getattr(models_module, 'Subsession')
        self.GroupClass = getattr(models_module, 'Group')
        self.PlayerClass = getattr(models_module, 'Player')

        self.player = self.PlayerClass.objects\
            .select_related(
                'group', 'subsession', 'session'
            ).get(pk=player_pk)

        self.group = self.player.group

        self.subsession = self.player.subsession
        self.session = self.player.session
        self.participant._round_number = self.subsession.round_number

        # for public API
        self.round_number = self.subsession.round_number

    @method_decorator(never_cache)
    @method_decorator(cache_control(must_revalidate=True, max_age=0,
                                    no_cache=True, no_store=True))
    def dispatch(self, request, *args, **kwargs):
        participant_code = kwargs.pop(constants.participant_code)

        with participant_lock(participant_code), otree.db.idmap.use_cache():

            self._index_in_pages = int(
                kwargs.pop(constants.index_in_pages))
            # temp, for page template
            self.index_in_pages = self._index_in_pages

            try:
                self.participant = Participant.objects.get(
                    code=participant_code)
            except Participant.DoesNotExist:
                msg = (
                    "This user ({}) does not exist in the database. "
                    "Maybe the database was recreated."
                ).format(participant_code)
                raise Http404(msg)

            # if the player tried to skip past a part of the subsession
            # (e.g. by typing in a future URL)
            # or if they hit the back button to a previous subsession
            # in the sequence.
            #
            if not self._user_is_on_right_page():
                # then bring them back to where they should be
                return self._redirect_to_page_the_user_should_be_on()

            self.load_objects()

            self.participant._current_page_name = self.__class__.__name__
            response = super(FormPageOrInGameWaitPageMixin, self).dispatch(
                request, *args, **kwargs)
            self.participant.last_request_succeeded = True
            self.participant._last_request_timestamp = time.time()

            # need to render the response before saving objects,
            # because the template might call a method that modifies
            # player/group/etc.
            if hasattr(response, 'render'):
                response.render()
            self.save_objects()
            return response

    # TODO: maybe this isn't necessary, because I can figure out what page
    # they should be on, from looking up index_in_pages
    def _user_is_on_right_page(self):
        """Will detect if a player tried to access a page they didn't reach
        yet, for example if they know the URL to the redemption code page,
        and try typing it in so they don't have to play the whole game.
        We should block that."""

        return self.request.path == self.participant._url_i_should_be_on()

    def _increment_index_in_pages(self):
        # when is this not the case?
        assert self._index_in_pages == self.participant._index_in_pages

        self._record_page_completion_time()
        # we should allow a user to move beyond the last page if it's mturk
        # also in general maybe we should show the 'out of sequence' page

        # the timeout record is irrelevant at this point, delete it
        # wait pages don't have a has_timeout attribute
        if hasattr(self, 'has_timeout') and self.has_timeout():
            PageTimeout.objects.filter(
                participant=self.participant,
                page_index=self.participant._index_in_pages).delete()
        # this is causing crashes because of the weird DB issue
        # ParticipantToPlayerLookup.objects.filter(
        #    participant=self.participant.pk,
        #    page_index=self.participant._index_in_pages).delete()

        # performance optimization:
        # we skip any page that is a sequence page where is_displayed
        # evaluates to False to eliminate unnecessary redirection
        views_module = otree.common_internal.get_views_module(
            self.subsession._meta.app_config.name)
        pages = views_module.page_sequence

        assert self.__class__ in pages
        pages_to_jump_by = 1
        indexes = list(range(self.player._index_in_game_pages + 1,
                             len(pages)))
        for target_index in indexes:
            Page = pages[target_index]

            # FIXME: are there other attributes? should i do As_view,
            # or simulate the
            # request?
            page = Page(player=self.player, group=self.group,
                        subsession=self.subsession, session=self.session)

            # don't skip wait pages
            # because the user has to pass through them
            # so we record that they visited
            if hasattr(Page, 'is_displayed') and not page.is_displayed():
                if hasattr(Page, '_tally_unvisited'):
                    page._index_in_pages = (
                        self._index_in_pages + pages_to_jump_by)
                    if page.wait_for_all_groups:
                        page._group_or_subsession = self.subsession
                    else:
                        page._group_or_subsession = self.group
                    with lock_on_this_code_path():
                        unvisited_participants = page._tally_unvisited()
                    # don't count myself; i only need to visit this page
                    # if everybody else already passed it
                    unvisited_participants.discard(self.participant.id)
                    if not unvisited_participants:
                        # if it's the last person
                        # because they need to complete the wait page
                        # don't skip past the wait page
                        break
                pages_to_jump_by += 1
            else:
                break

        self.player._index_in_game_pages += pages_to_jump_by
        self.participant._index_in_pages += pages_to_jump_by

        channels.Group(
            'auto-advance-{}'.format(self.participant.code)
        ).send(
            {'text': json.dumps(
                {'new_index_in_pages': self.participant._index_in_pages})}
        )

    def is_displayed(self):
        return True

    def _record_page_completion_time(self):

        now = int(time.time())

        last_page_timestamp = self.participant._last_page_timestamp
        if last_page_timestamp is None:
            logger.warning(
                'Participant {}: _last_page_timestamp is None'.format(
                    self.participant.code))
            last_page_timestamp = now

        seconds_on_page = now - last_page_timestamp

        self.participant._last_page_timestamp = now
        page_name = self.__class__.__name__

        timeout_happened = bool(
            hasattr(self, 'timeout_happened') and self.timeout_happened
        )

        PageCompletion.objects.create(
            app_name=self.subsession._meta.app_config.name,
            page_index=self._index_in_pages,
            page_name=page_name, time_stamp=now,
            seconds_on_page=seconds_on_page,
            subsession_pk=self.subsession.pk,
            participant=self.participant,
            session=self.session,
            auto_submitted=timeout_happened)
        self.participant.save()


class GenericWaitPageMixin(object):
    """used for in-game wait pages, as well as other wait-type pages oTree has
    (like waiting for session to be created, or waiting for players to be
    assigned to matches

    """

    def socket_url(self):
        '''called from template'''
        raise NotImplementedError()

    def redirect_url(self):
        '''called from template'''
        # need get_full_path because we use query string here
        return self.request.get_full_path()

    def get_template_names(self):
        """fallback to otree/WaitPage.html, which is guaranteed to exist.
        the reason for the 'if' statement, rather than returning a list,
        is that if the user explicitly defined template_name, and that template
        does not exist, then we should not fail silently.
        (for example, the user forgot to add it to git)
        """
        if self.template_name:
            return [self.template_name]
        return ['global/WaitPage.html', 'otree/WaitPage.html']

    def _get_wait_page(self):
        response = TemplateResponse(
            self.request, self.get_template_names(), self.get_context_data())
        response[constants.wait_page_http_header] = (
            constants.get_param_truth_value)
        return response

    def _before_returning_wait_page(self):
        pass

    def _response_when_ready(self):
        raise NotImplementedError()

    def dispatch(self, request, *args, **kwargs):
        if self._is_ready():
            return self._response_when_ready()
        self._before_returning_wait_page()
        return self._get_wait_page()

    title_text = None

    body_text = None

    def _get_default_title_text(self):
        # Translators: the default title of a wait page
        return _('Please wait')

    def _get_default_body_text(self):
        return ''

    def get_context_data(self, **kwargs):
        # 2015-11-13: title_text() and body_text() methods deprecated
        # they should be class attributes instead
        title_text = self.title_text
        if callable(title_text):
            title_text = title_text()
        body_text = self.body_text
        if callable(body_text):
            body_text = body_text()

        # could evaluate to false like 0
        if title_text is None:
            title_text = self._get_default_title_text()
        if body_text is None:
            body_text = self._get_default_body_text()

        context = {
            'title_text': title_text,
            'body_text': body_text,
        }

        # default title/body text can be overridden
        # if user specifies it in vars_for_template
        context.update(
            super(GenericWaitPageMixin, self).get_context_data(**kwargs)
        )

        return context


class InGameWaitPageMixin(object):
    """Wait pages during game play (i.e. checkpoints),
    where users wait for others to complete

    """

    def dispatch(self, request, *args, **kwargs):
        self._group_or_subsession = (
            self.subsession if self.wait_for_all_groups else self.group)
        if self._is_ready():
            return self._response_when_ready()
        # take a lock because we set "waiting for" list here
        with lock_on_this_code_path():
            unvisited_participants = self._tally_unvisited()
        if unvisited_participants:
            # only skip the wait page if there are still
            # unvisited participants. otherwise, you need to
            # mark the page as completed.
            # see _increment_index_in_pages, which needs to
            # handle this case also
            if not self.is_displayed():
                return self._response_when_ready()
            self.participant.is_on_wait_page = True
            return self._get_wait_page()

        try:
            if self.wait_for_all_groups:
                completion = CompletedSubsessionWaitPage(
                    page_index=self._index_in_pages,
                    session=self.session
                )
            else:
                completion = CompletedGroupWaitPage(
                    page_index=self._index_in_pages,
                    group_pk=self.group.pk,
                    session=self.session
                )
            completion.save()
        # if the record already exists
        # (enforced through unique_together)
        except django.db.IntegrityError:
            self.participant.is_on_wait_page = True
            return self._get_wait_page()
        try:
            # need to check this before deleting
            # reference to self.player
            is_displayed = self.is_displayed()

            # in case there is a timeout on the next page, we
            # should ensure the next pages are visited promptly
            # TODO: can we make this run only if next page is a
            # timeout page?
            # or if a player is auto playing.
            # we could instead make this request the current page
            # URL, but it's different for each player

            # _group_or_subsession might be deleted
            # in after_all_players_arrive, so calculate this first
            participant_pk_set = set(
                self._group_or_subsession.player_set
                .values_list('participant__pk', flat=True))

            # _group_or_subsession might be deleted
            # in after_all_players_arrive, so calculate this first
            channels_group_name = self.channels_group_name()

            # block users from accessing self.player inside
            # after_all_players_arrive, because conceptually
            # there is no single player in this context
            # (method is executed once for the whole group)

            player = self.player
            del self.player

            # make sure we get the most up-to-date player objects
            # e.g. if they were queried in is_displayed(),
            # then they could be out of date
            # but don't delete the current player from cache
            # because we need it to be saved at the end
            import idmap.tls
            cache = getattr(idmap.tls._tls, 'idmap_cache', {})
            for p in list(cache.get(self.PlayerClass, {}).values()):
                if p != player:
                    self.PlayerClass.flush_cached_instance(p)

            # if any player can skip the wait page,
            # then we shouldn't run after_all_players_arrive
            # because if some players are able to proceed to the next page
            # before after_all_players_arrive is run,
            # then after_all_players_arrive is probably not essential.
            # often, there are some wait pages that all players skip,
            # because they should only be shown in certain rounds.
            # maybe the fields that after_all_players_arrive depends on
            # are null
            # something to think about: ideally, should we check if
            # all players skipped, or any player skipped?
            # as a shortcut, we just check if is_displayed is true
            # for the last player.
            if is_displayed:
                self.after_all_players_arrive()
        except:
            completion.delete()
            raise

        self.player = player

        if otree.common_internal.USE_REDIS:
            # 2015-07-27:
            #   why not check if the next page has_timeout?
            otree.timeout.tasks.ensure_pages_visited.schedule(
                kwargs={
                    'participant_pk_set': participant_pk_set,
                    'wait_page_index': self._index_in_pages}, delay=10)

        completion.after_all_players_arrive_run = True
        completion.save()

        # send a message to the channel to move forward
        # this should happen at the very end,
        channels.Group(channels_group_name).send(
            {'text': json.dumps(
                {'status': 'ready'})}
        )

        # we can assume it's ready because
        # even if it wasn't created, that means someone else
        # created it, and therefore that whole code block
        # finished executing (including the after_all_players_arrive)
        # inside the transaction
        return self._response_when_ready()

    def channels_group_name(self):
        model_name = 'subsession' if self.wait_for_all_groups else 'group'

        return otree.common_internal.channels_wait_page_group_name(
            session_pk=self.session.pk,
            page_index=self._index_in_pages,
            model_name=model_name,
            model_pk=self._group_or_subsession.pk)

    def socket_url(self):
        model_name = 'subsession' if self.wait_for_all_groups else 'group'

        params = ','.join([
            str(self.session.pk),
            str(self._index_in_pages),
            model_name,
            str(self._group_or_subsession.pk)
        ])

        return '/wait_page/{}/'.format(params)

    def _is_ready(self):
        """all participants visited, AND action has been run"""
        if self.wait_for_all_groups:
            return CompletedSubsessionWaitPage.objects.filter(
                page_index=self._index_in_pages,
                session=self.session,
                after_all_players_arrive_run=True).exists()
        return CompletedGroupWaitPage.objects.filter(
            page_index=self._index_in_pages,
            group_pk=self.group.pk,
            session=self.session,
            after_all_players_arrive_run=True).exists()

    def _tally_unvisited(self):
        """side effect: set _waiting_for_ids"""

        participant_ids = set(
            self._group_or_subsession.player_set.values_list(
                'participant_id', flat=True))

        participant_data = Participant.objects.filter(
            id__in=participant_ids
        ).values('id', 'id_in_session', '_index_in_pages')

        visited = []
        unvisited = []
        for p in participant_data:
            if p['_index_in_pages'] < self._index_in_pages:
                unvisited.append(p)
            else:
                visited.append(p)

        if 1 <= len(unvisited) <= 3:

            unvisited_description = ', '.join(
                'P{}'.format(p['id_in_session']) for p in unvisited)

            visited_ids = [p['id'] for p in visited]
            Participant.objects.filter(
                id__in=visited_ids
            ).update(_waiting_for_ids=unvisited_description)

        return {p['id'] for p in unvisited}

    def is_displayed(self):
        return True

    def _response_when_ready(self):
        self.participant.is_on_wait_page = False
        self.participant._waiting_for_ids = None
        self._increment_index_in_pages()
        return self._redirect_to_page_the_user_should_be_on()

    def after_all_players_arrive(self):
        pass

    def _get_default_body_text(self):
        num_other_players = len(self._group_or_subsession.get_players()) - 1
        if num_other_players > 1:
            return _('Waiting for the other participants.')
        if num_other_players == 1:
            return _('Waiting for the other participant.')
        return ''


class BrowserBot(object):

    def __init__(self, view):
        self.view = view
        self.participant = view.participant
        self.session = view.session
        self.send_finished_message = False
        self.input_is_valid = True

    def get_submission(self):
        # request.POST contains CSRF token and maybe other important stuff
        post_data = dict(self.view.request.POST)
        submit_model = BrowserBotSubmit.objects.order_by('id').filter(
            participant=self.participant,
        ).first()
        if submit_model:
            this_page_dotted = '{}.{}'.format(
                self.view.__module__,
                self.view.__class__.__name__
            )
            if not submit_model.page_dotted_name == this_page_dotted:
                raise ValueError(
                    "Bot is trying to submit page {}, "
                    "but current page is {}. "
                    "Check your bot in tests.py, "
                    "then create a new session.".format(
                        submit_model.page_dotted_name,
                        this_page_dotted
                    )
                )
            post_data.update(submit_model.param_dict)
            self.input_is_valid = submit_model.input_is_valid
            self.send_finished_message = submit_model.is_last
            submit_model.delete()

        return post_data

    def check_if_finished(self):
        if self.send_finished_message:
            HUEY.storage.conn.rpush(
                self.session.code, True)


class FormPageMixin(object):
    """mixin rather than subclass because we want these methods only to be
    first in MRO

    """

    # if a model is not specified, use empty "StubModel"
    model = StubModel
    fields = []

    def get_template_names(self):
        if self.template_name is not None:
            return [self.template_name]
        return ['{}/{}.html'.format(
            get_app_label_from_import_path(self.__module__),
            self.__class__.__name__)]

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
        return otree.forms.modelform_factory(
            self.form_model, fields=fields,
            form=otree.forms.ModelForm,
            formfield_callback=otree.forms.formfield_callback)

    def before_next_page(self):
        pass

    def get_form(self, data=None, files=None, **kwargs):
        """Given `data` and `files` QueryDicts, and optionally other named
        arguments, and returns a form.

        """
        cls = self.get_form_class()
        return cls(data=data, files=files, view=self, **kwargs)

    def form_invalid(self, form):
        response = super(FormPageMixin, self).form_invalid(form)
        response[constants.redisplay_with_errors_http_header] = (
            constants.get_param_truth_value)
        return response

    def get(self, request, *args, **kwargs):
        if not self.is_displayed():
            self._increment_index_in_pages()
            return self._redirect_to_page_the_user_should_be_on()

        self.participant._current_form_page_url = self.request.path
        if otree.common_internal.USE_REDIS:
            if self.participant._is_auto_playing:
                otree.timeout.tasks.submit_expired_url.schedule(
                    (self.request.path,), delay=2)  # 2 seconds
            elif self.has_timeout():
                otree.timeout.tasks.submit_expired_url.schedule(
                    (self.request.path,), delay=self.timeout_seconds)

        return super(FormPageMixin, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):

        self.object = self.get_object()

        if request.POST.get(constants.auto_submit):
            self.timeout_happened = True  # for public API
            self._set_auto_submit_values()
        else:
            self.timeout_happened = False
            use_browser_bots = self.session._use_browser_bots
            if use_browser_bots:
                bot = BrowserBot(view=self)
                post_data = bot.get_submission()
            else:
                post_data = request.POST
            form = self.get_form(
                data=post_data, files=request.FILES, instance=self.object)
            if form.is_valid():
                self.form = form
                self.object = form.save()
                if use_browser_bots:
                    bot.check_if_finished()
            else:
                if use_browser_bots and not bot.input_is_valid:
                    errors = [
                        "{}: {}".format(k, repr(v))
                        for k, v in form.errors.items()]
                    raise ValueError(
                        'Some fields failed validation: {} '
                        'Check your bot in tests.py, '
                        'then create a new session.'.format(
                            errors
                        )
                    )
                return self.form_invalid(form)
        self.before_next_page()
        self._increment_index_in_pages()
        return self._redirect_to_page_the_user_should_be_on()

    def socket_url(self):
        '''called from template. can't start with underscore because used
        in template

        '''
        params = ','.join([self.participant.code, str(self._index_in_pages)])
        return '/auto_advance/{}/'.format(params)

    def redirect_url(self):
        '''called from template'''
        # need full path because we use query string
        return self.request.get_full_path()

    def _get_auto_submit_values(self):
        # TODO: auto_submit_values deprecated on 2015-05-28
        auto_submit_values = getattr(self, 'auto_submit_values', {})
        timeout_submission = self.timeout_submission or auto_submit_values
        for field_name in self.form_fields:
            if field_name not in timeout_submission:
                # get default value for datatype if the user didn't specify
                ModelField = self.form_model._meta.get_field_by_name(
                    field_name
                )[0]
                # TODO: should we warn if the attribute doesn't exist?
                value = getattr(ModelField, 'auto_submit_default', None)
                timeout_submission[field_name] = value
        return timeout_submission

    def _set_auto_submit_values(self):
        auto_submit_dict = self._get_auto_submit_values()
        for field_name in auto_submit_dict:
            setattr(self.object, field_name, auto_submit_dict[field_name])

    def has_timeout(self):
        return self.timeout_seconds is not None and self.timeout_seconds > 0

    def remaining_timeout_seconds(self):
        if not self.has_timeout():
            return
        current_time = int(time.time())
        expiration_time = current_time + self.timeout_seconds
        timeout, created = PageTimeout.objects.get_or_create(
            participant=self.participant,
            page_index=self.participant._index_in_pages,
            defaults={'expiration_time': expiration_time})

        return timeout.expiration_time - current_time

    timeout_seconds = None


class PlayerUpdateView(FormPageMixin, FormPageOrInGameWaitPageMixin,
                       vanilla.UpdateView):

    def get_object(self):
        Cls = self.form_model
        if Cls == self.GroupClass:
            return self.group
        if Cls == self.PlayerClass:
            return self.player
        if Cls == StubModel:
            return StubModel.objects.all()[0]


class InGameWaitPage(FormPageOrInGameWaitPageMixin, InGameWaitPageMixin,
                     GenericWaitPageMixin, vanilla.UpdateView):
    """public API wait page

    """
    pass


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
        return r"^{}/(?P<code>[a-z0-9]+)/$".format(cls.__name__)

    @classmethod
    def url(cls, session_code):
        return '/{}/{}/'.format(cls.__name__, session_code)

    def get_context_data(self, **kwargs):
        context = super(AdminSessionPageMixin, self).get_context_data(**kwargs)
        context.update({
            'session': self.session,
            'is_debug': settings.DEBUG})
        return context

    def get_template_names(self):
        return ['otree/admin/{}.html'.format(self.__class__.__name__)]

    def dispatch(self, request, *args, **kwargs):
        session_code = kwargs['code']
        self.session = get_object_or_404(
            otree.models.Session, code=session_code)
        return super(AdminSessionPageMixin, self).dispatch(
            request, *args, **kwargs)
