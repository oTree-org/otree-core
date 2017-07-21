# -*- coding: utf-8 -*-

# =============================================================================
# IMPORTS
# =============================================================================

import contextlib
import importlib
import json
import logging
import time
import warnings

import channels
import django.db
import redis_lock
import vanilla
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import resolve
from django.db.models import Max
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.decorators.cache import never_cache, cache_control
from six.moves import range

import otree.common_internal
import otree.constants_internal as constants
import otree.db.idmap
import otree.forms
import otree.models
import otree.timeout.tasks
from otree.bots.bot import bot_prettify_post_data
from otree.bots.browser import EphemeralBrowserBot
from otree.common_internal import (
    get_app_label_from_import_path, get_dotted_name, get_admin_secret_code,
    DebugTable, BotError)
from otree.models import Participant
from otree.models_concrete import (
    PageCompletion, CompletedSubsessionWaitPage,
    CompletedGroupWaitPage, PageTimeout, UndefinedFormModel,
    ParticipantLockModel, GlobalLockModel
)

# Get an instance of a logger
logger = logging.getLogger(__name__)

NO_PARTICIPANTS_LEFT_MSG = (
    "The maximum number of participants for this session has been exceeded.")

ADMIN_SECRET_CODE = get_admin_secret_code()


def get_view_from_url(url):
    view_func = resolve(url).func
    module = importlib.import_module(view_func.__module__)
    Page = getattr(module, view_func.__name__)
    return Page


@contextlib.contextmanager
def global_lock(recheck_interval=0.1):
    TIMEOUT = 10
    start_time = time.time()
    while time.time() - start_time < TIMEOUT:
        updated_locks = GlobalLockModel.objects.filter(
            locked=False
        ).update(locked=True)
        if not updated_locks:
            time.sleep(recheck_interval)
        else:
            try:
                yield
            finally:
                GlobalLockModel.objects.update(locked=False)
            return

    # could happen if the request that has the lock is paused somehow,
    # e.g. in a debugger
    raise Exception('Another HTTP request has the global lock.')


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

    # could happen if the request that has the lock is paused somehow,
    # e.g. in a debugger
    raise Exception(
        'Another HTTP request has the lock for participant {}.'.format(
            participant_code))


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

    def _redirect_to_page_the_user_should_be_on(self):
        """Redirect to where the player should be,
        according to the view index we maintain in the DB
        Useful if the player tried to skip ahead,
        or if they hit the back button.
        We can put them back where they belong.
        """

        return HttpResponseRedirect(self.participant._url_i_should_be_on())


class FormPageOrInGameWaitPageMixin(OTreeMixin):
    """
    View that manages its position in the group sequence.
    for both players and experimenters
    """

    @classmethod
    def url_pattern(cls, name_in_url):
        p = r'^p/(?P<participant_code>\w+)/{}/{}/(?P<page_index>\d+)/$'.format(
            name_in_url,
            cls.__name__,
        )
        return p

    @classmethod
    def url_name(cls):
        '''using dots seems not to work'''
        return get_dotted_name(cls).replace('.', '-')

    @method_decorator(never_cache)
    @method_decorator(cache_control(must_revalidate=True, max_age=0,
                                    no_cache=True, no_store=True))
    def dispatch(self, request, *args, **kwargs):

        participant_code = kwargs.pop(constants.participant_code)

        if otree.common_internal.USE_REDIS:
            lock = redis_lock.Lock(
                otree.common_internal.get_redis_conn(),
                participant_code,
                expire=60,
                auto_renewal=True
            )
        else:
            lock = participant_lock(participant_code)

        with lock, otree.db.idmap.use_cache():
            try:
                participant = Participant.objects.get(
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
            url_should_be_on = participant._url_i_should_be_on()
            if not self.request.path == url_should_be_on:
                return HttpResponseRedirect(url_should_be_on)

            self.set_attributes(participant)

            self.participant._current_page_name = self.__class__.__name__
            response = super(FormPageOrInGameWaitPageMixin, self).dispatch(
                request, *args, **kwargs)
            self.participant._last_request_timestamp = time.time()

            # need to render the response before saving objects,
            # because the template might call a method that modifies
            # player/group/etc.
            if hasattr(response, 'render'):
                response.render()
            self.save_objects()
            if (
                    self.session.use_browser_bots and
                    'browser-bot-auto-submit' in response.content.decode(
                            'utf-8')):
                bot = EphemeralBrowserBot(self)
                bot.prepare_next_submit(response.content.decode('utf-8'))
            return response

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

            # doesn't exist on wait pages, so need getattr
            'timer_text': getattr(self, 'timer_text', None)
        })

        vars_for_template = {}
        views_module = otree.common_internal.get_views_module(
            self.subsession._meta.app_config.name)
        if hasattr(views_module, 'vars_for_all_templates'):
            vars_for_template.update(views_module.vars_for_all_templates(self) or {})

        vars_for_template.update(self.vars_for_template() or {})
        self._vars_for_template = vars_for_template

        context.update(vars_for_template)

        if settings.DEBUG:
            self.debug_tables = self._get_debug_tables()
        return context

    def vars_for_template(self):
        return {}

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
            new_tables.append(DebugTable(title='Vars for template', rows=rows))

        return new_tables

    # make these properties so they can be calculated lazily,
    # in _increment_index
    _player = None
    _group = None
    _subsession = None
    _session = None
    _round_number = None

    @property
    def player(self):
        if not self._player:
            player_pk = self.participant.player_lookup()['player_pk']
            self._player = self.PlayerClass.objects.get(pk=player_pk)
        return self._player

    @property
    def group(self):
        if not self._group:
            self._group = self.player.group
        return self._group

    @property
    def subsession(self):
        if not self._subsession:
            self._subsession = self.player.subsession
        return self._subsession

    @property
    def session(self):
        if not self._session:
            self._session = self.participant.session
        return self._session

    @property
    def round_number(self):
        if self._round_number is None:
            self._round_number = self.player.round_number
        return self._round_number

    @player.setter
    def player(self, value):
        self._player = value

    @group.setter
    def group(self, value):
        self._group = value

    @subsession.setter
    def subsession(self, value):
        self._subsession = value

    @session.setter
    def session(self, value):
        self._session = value

    @round_number.setter
    def round_number(self, value):
        self._round_number = value

    def set_attributes(self, participant, lazy=False):
        """
        Even though we only use PlayerClass in set_attributes,
        we use {Group/Subsession}Class elsewhere.

        2015-05-07: shouldn't this go in oTreeMixin?
        because used by all views, not just sequence
        """

        self.participant = participant

        # it's already validated that participant is on right page
        self._index_in_pages = participant._index_in_pages

        # temp, for page template
        self.index_in_pages = self._index_in_pages

        player_lookup = participant.player_lookup()

        app_name = player_lookup['app_name']
        player_pk = player_lookup['player_pk']

        # for the participant changelist
        self.participant._current_app_name = app_name

        models_module = otree.common_internal.get_models_module(app_name)
        self._models_module = models_module
        self.SubsessionClass = getattr(models_module, 'Subsession')
        self.GroupClass = getattr(models_module, 'Group')
        self.PlayerClass = getattr(models_module, 'Player')

        if not lazy:
            self.player = self.PlayerClass.objects\
                .select_related(
                    'group', 'subsession', 'session'
                ).get(pk=player_pk)
            self.session = self.player.session
            self.participant._round_number = self.player.round_number
            self.group = self.player.group
            self.subsession = self.player.subsession

            # for public API
            self.round_number = self.subsession.round_number

    def _increment_index_in_pages(self):
        # when is this not the case?
        assert self._index_in_pages == self.participant._index_in_pages

        self._record_page_completion_time()
        # we should allow a user to move beyond the last page if it's mturk
        # also in general maybe we should show the 'out of sequence' page

        # this is causing crashes because of the weird DB issue
        # ParticipantToPlayerLookup.objects.filter(
        #    participant=self.participant.pk,
        #    page_index=self.participant._index_in_pages).delete()

        # we skip any page that is a sequence page where is_displayed
        # evaluates to False to eliminate unnecessary redirection

        for page_index in range(
                # go to max_page_index+2 because range() skips the last index
                # and it's possible to go to max_page_index + 1 (OutOfRange)
                self._index_in_pages+1, self.participant._max_page_index+2):
            self.participant._index_in_pages = page_index
            if page_index == self.participant._max_page_index+1:
                # break and go to OutOfRangeNotification
                break
            url = self.participant._url_i_should_be_on()

            Page = get_view_from_url(url)
            page = Page()

            page.set_attributes(self.participant, lazy=True)
            if page.is_displayed():
                break

            # if it's a wait page, record that they visited
            # but don't run after_all_players_arrive
            if hasattr(page, '_check_if_complete'):

                if page.group_by_arrival_time:
                    # keep looping
                    continue

                # save the participant, because tally_unvisited
                # queries index_in_pages directly from the DB
                # this fixes a bug reported on 2016-11-04 on the mailing list
                self.participant.save()
                # you could just return page.dispatch(),
                # but that could cause deep recursion

                completion = page._check_if_complete()
                if completion:
                    # mark it fully completed right away,
                    # since we don't run after_all_players_arrive()
                    completion.fully_completed = True
                    completion.save()
                    participant_pk_set = set(
                        page._group_or_subsession.player_set.values_list(
                            'participant__pk', flat=True))
                    page.send_completion_message(participant_pk_set)

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



_MSG_Undefined_GetPlayersForGroup = (
    'You cannot reference self.player, self.group, or self.participant '
    'inside get_players_for_group.'
)

_MSG_Undefined_AfterAllPlayersArrive_Player = (
    'self.player and self.participant cannot be referenced '
    'inside after_all_players_arrive, '
    'which is executed only once '
    'for the entire group.'
)

_MSG_Undefined_AfterAllPlayersArrive_Group = (
    'self.group cannot be referenced inside after_all_players_arrive '
    'if wait_for_all_groups=True, '
    'because after_all_players_arrive() is executed only once '
    'for all groups in the subsession.'
)

class Undefined_AfterAllPlayersArrive_Player:
    def __getattribute__(self, item):
        raise AttributeError(_MSG_Undefined_AfterAllPlayersArrive_Player)

    def __setattr__(self, item, value):
        raise AttributeError(_MSG_Undefined_AfterAllPlayersArrive_Player)


class Undefined_AfterAllPlayersArrive_Group:
    def __getattribute__(self, item):
        raise AttributeError(_MSG_Undefined_AfterAllPlayersArrive_Group)

    def __setattr__(self, item, value):
        raise AttributeError(_MSG_Undefined_AfterAllPlayersArrive_Group)


class Undefined_GetPlayersForGroup:

    def __getattribute__(self, item):
        raise AttributeError(_MSG_Undefined_GetPlayersForGroup)

    def __setattr__(self, item, value):
        raise AttributeError(_MSG_Undefined_GetPlayersForGroup)



class InGameWaitPageMixin(object):
    """
    Wait pages during game play (i.e. checkpoints),
    where users wait for others to complete
    """
    wait_for_all_groups = False
    group_by_arrival_time = False

    def dispatch(self, *args, **kwargs):

        if self._is_fully_completed():
            # need to deactivate cache, in case after_all_players_arrive
            # finished running after the moment set_attributes
            # was called in this request.

            # because in response_when_ready we will call
            # increment_index_in_pages, which does a look-ahead and calls
            # is_displayed() on the following pages. is_displayed() might
            # depend on a field that is set in after_all_players_arrive
            # so, need to clear the cache to ensure
            # that we get fresh data.

            # Note: i was never able to reproduce this myself -- just heard
            # from Anthony N.
            # and it shouldn't happen, because only the last player to visit
            # can set is_ready(). if there is a request coming after that,
            # then it must be someone refreshing the page manually.
            # i guess we should protect against that.

            # is_displayed() could also depend on a field on participant
            # that was set on the wait page, so need to refresh participant,
            # because it is passed as an arg to set_attributes().

            otree.db.idmap.save_objects()
            otree.db.idmap.flush_cache()
            self.participant.refresh_from_db()

            return self._response_when_ready()

        if self.group_by_arrival_time:
            if self.is_displayed():
                if otree.common_internal.USE_REDIS:
                    lock = redis_lock.Lock(
                        otree.common_internal.get_redis_conn(),
                        'group_by_arrival_time',
                        #self.get_channels_group_name(),
                        expire=60,
                        auto_renewal=True
                    )
                else:
                    lock = global_lock()
                with lock:
                    regrouped = self._try_to_regroup()
                    if not regrouped:
                        return self._get_wait_page()
                # because group may have changed
                self.group = self.player.group
            else:
                return self._response_when_ready()

        # take a lock because we set "waiting for" list here
        completion = self._check_if_complete()
        if not completion:
            if self.is_displayed():
                self.participant.is_on_wait_page = True
                return self._get_wait_page()
            else:
                return self._response_when_ready()

        # the group membership might be modified
        # in after_all_players_arrive, so calculate this first
        participant_pk_set = set(
            self._group_or_subsession.player_set
            .values_list('participant__pk', flat=True))

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
        if self.is_displayed():
            self._run_after_all_players_arrive(completion)

        # even if this player skips the page and after_all_players_arrive
        # is not run, we need to indicate that the waiting players can advance

        completion.fully_completed = True
        completion.save()

        self.send_completion_message(participant_pk_set)
        return self._response_when_ready()

    def _run_after_all_players_arrive(self, completion):
        try:
            # block users from accessing self.player inside
            # after_all_players_arrive, because conceptually
            # there is no single player in this context
            # (method is executed once for the whole group).
            # same idea with self.group, if we're waiting for all
            # groups, not just one.

            current_player = self.player
            current_participant = self.participant
            # set to UNDEFINED rather than None,
            # because then it won't be loaded lazily
            self.player = self.participant = Undefined_AfterAllPlayersArrive_Player()
            if self.wait_for_all_groups:
                current_group = self.group
                self.group = Undefined_AfterAllPlayersArrive_Group()

            # make sure we get the most up-to-date player objects
            # e.g. if they were queried in is_displayed(),
            # then they could be out of date
            # but don't delete the current player from cache
            # because we need it to be saved at the end
            import idmap.tls
            cache = getattr(idmap.tls._tls, 'idmap_cache', {})
            for p in list(cache.get(self.PlayerClass, {}).values()):
                if p != current_player:
                    self.PlayerClass.flush_cached_instance(p)
            self.after_all_players_arrive()

            # need to save to the results of after_all_players_arrive
            # to the DB, before sending the completion message to other players
            # this was causing a race condition on 2016-11-04
            otree.db.idmap.save_objects()
        except:
            completion.delete()
            raise

        # restore what we deleted earlier
        # 2016-11-09: is this code even needed? because i don't think
        # self.player and self.group is referenced after this point.
        # anyway, the group could be deleted in after_all_players_arrive.

        self.player = current_player
        self.participant = current_participant
        if self.wait_for_all_groups:
            self.group = current_group

    @property
    def _group_or_subsession(self):
        return self.subsession if self.wait_for_all_groups else self.group

    def _check_if_complete(self):
        if otree.common_internal.USE_REDIS:
            lock = redis_lock.Lock(
                otree.common_internal.get_redis_conn(),
                self.get_channels_group_name(),
                expire=60,
                auto_renewal=True
            )
        else:
            lock = global_lock()
        with lock:
            unvisited_participants = self._tally_unvisited()
        if unvisited_participants:
            return
        try:
            if self.wait_for_all_groups:
                completion = CompletedSubsessionWaitPage(
                    page_index=self._index_in_pages,
                    session=self.session
                )
            else:
                completion = CompletedGroupWaitPage(
                    page_index=self._index_in_pages,
                    id_in_subsession=self.group.id_in_subsession,
                    session=self.session
                )
            completion.save()
            return completion
        # if the record already exists
        # (enforced through unique_together)
        except django.db.IntegrityError:
            return

    def _try_to_regroup(self):
        if self.player._group_by_arrival_time_grouped:
            return False

        GroupClass = type(self.group)

        self.player._group_by_arrival_time_arrived = True
        self.player._group_by_arrival_time_timestamp = (
            self.player._group_by_arrival_time_timestamp or time.time())

        self.player.save()
        # count how many are re-grouped
        waiting_players = list(self.subsession.player_set.filter(
            _group_by_arrival_time_arrived=True,
            _group_by_arrival_time_grouped=False,
        ).order_by('_group_by_arrival_time_timestamp'))

        # prevent the user
        current_player = self.player
        current_participant = self.participant
        current_group = self.group

        self.player = self.participant = self.group = Undefined_GetPlayersForGroup()

        players_for_group = self.get_players_for_group(waiting_players)

        # restore hidden attributes
        self.player = current_player
        self.participant = current_participant
        self.group = current_group


        if not players_for_group:
            return False
        participant_ids = [p.participant.id for p in players_for_group]

        group_id_in_subsession = self._next_group_id_in_subsession()

        Constants = self._models_module.Constants

        with otree.common_internal.transaction_except_for_sqlite():
            for round_number in range(self.round_number, Constants.num_rounds+1):
                subsession = self.subsession.in_round(round_number)

                unordered_players = subsession.player_set.filter(
                    participant_id__in=participant_ids)

                participant_ids_to_players = {
                    player.participant.id: player for player in unordered_players}

                ordered_players_for_group = [
                    participant_ids_to_players[participant_id]
                    for participant_id in participant_ids]

                if round_number == self.round_number:
                    for player in ordered_players_for_group:
                        player._group_by_arrival_time_grouped = True
                        player.save()

                group = GroupClass.objects.create(
                    subsession=subsession, id_in_subsession=group_id_in_subsession,
                    session=self.session, round_number=round_number)
                group.set_players(ordered_players_for_group)

                # prune groups without players
                # apparently player__isnull=True works, didn't know you could
                # use this in a reverse direction.
                subsession.group_set.filter(player__isnull=True).delete()

        return True

    def get_players_for_group(self, waiting_players):
        Constants = self._models_module.Constants

        if Constants.players_per_group is None:
            raise AssertionError(
                'Page "{}": if using group_by_arrival_time, you must either set '
                'Constants.players_per_group to a value other than None, '
                'or define get_players_for_group() on the page.'.format(
                    self.__class__.__name__
                )
            )

        # we're locking, so it shouldn't be more
        assert len(waiting_players) <= Constants.players_per_group

        if len(waiting_players) == Constants.players_per_group:
            return waiting_players



    def send_completion_message(self, participant_pk_set):

        if otree.common_internal.USE_REDIS:
            # 2016-11-15: we used to only ensure the next page is visited
            # if the next page has a timeout, or if it's a wait page
            # but this is not reliable because next page might be skipped anyway,
            # and we don't know what page will actually be shown next to the user.
            otree.timeout.tasks.ensure_pages_visited.schedule(
                kwargs={
                    'participant_pk_set': participant_pk_set},
                delay=10)

        # _group_or_subsession might be deleted
        # in after_all_players_arrive, but it won't delete the cached model
        channels_group_name = self.get_channels_group_name()
        channels.Group(channels_group_name).send(
            {'text': json.dumps(
                {'status': 'ready'})}
        )

    def _next_group_id_in_subsession(self):
        # 2017-05-05: seems like this can result in id_in_subsession that
        # doesn't start from 1.
        # especially if you do group_by_arrival_time in every round
        # is that a problem?
        res = type(self.group).objects.filter(
            session=self.session).aggregate(Max('id_in_subsession'))
        return res['id_in_subsession__max'] + 1

    def _channels_group_id_in_subsession(self):
        if self.wait_for_all_groups:
            return ''
        return self.group.id_in_subsession

    def get_channels_group_name(self):
        if self.group_by_arrival_time:
            return otree.common_internal.channels_group_by_arrival_time_group_name(
                session_pk=self.session.pk, page_index=self._index_in_pages,
            )
        group_id_in_subsession = self._channels_group_id_in_subsession()

        return otree.common_internal.channels_wait_page_group_name(
            session_pk=self.session.pk,
            page_index=self._index_in_pages,
            group_id_in_subsession=group_id_in_subsession)

    def socket_url(self):
        if self.group_by_arrival_time:
            return '/group_by_arrival_time/{},{},{},{}/'.format(
                self.session.id, self._index_in_pages,
                self.player._meta.app_config.name, self.player.id)

        group_id_in_subsession = self._channels_group_id_in_subsession()

        return '/wait_page/{},{},{}/'.format(
            self.session.pk,
            self._index_in_pages,
            group_id_in_subsession
        )

    def _is_fully_completed(self):
        """all participants visited, AND action has been run"""
        if self.wait_for_all_groups:
            return CompletedSubsessionWaitPage.objects.filter(
                page_index=self._index_in_pages,
                session=self.session,
                fully_completed=True).exists()
        return CompletedGroupWaitPage.objects.filter(
            page_index=self._index_in_pages,
            id_in_subsession=self.group.id_in_subsession,
            session=self.session,
            fully_completed=True).exists()

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


class FormPageMixin(object):
    """mixin rather than subclass because we want these methods only to be
    first in MRO

    """

    # if a model is not specified, use empty "StubModel"
    form_model = UndefinedFormModel
    form_fields = []

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
        if self.form_model is UndefinedFormModel and fields:
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

        fields_with_errors = [
            fname for fname in form.errors
            if fname != '__all__']

        if fields_with_errors:
            self.first_field_with_errors = fields_with_errors[0]
            self.other_fields_with_errors = fields_with_errors[1:]

        return response

    def get(self, request, *args, **kwargs):
        if not self.is_displayed():
            self._increment_index_in_pages()
            return self._redirect_to_page_the_user_should_be_on()

        # this needs to be set AFTER scheduling submit_expired_url,
        # to prevent race conditions.
        # see that function for an explanation.
        self.participant._current_form_page_url = self.request.path
        return super(FormPageMixin, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):

        self.object = self.get_object()

        if self.session.use_browser_bots:
            bot = EphemeralBrowserBot(self)
            try:
                submission = bot.get_next_post_data()
            except StopIteration:
                bot.send_completion_message()
                return HttpResponse('Bot completed')
            else:
                # convert MultiValueKeyDict to regular dict
                # so that we can add entries to it in a simple way
                # before, we used dict(request.POST), but that caused
                # errors with BooleanFields with blank=True that were
                # submitted empty...it said [''] is not a valid value
                post_data = request.POST.dict()
                post_data.update(submission)
        else:
            post_data = request.POST

        form = self.get_form(
                data=post_data, files=request.FILES, instance=self.object)
        self.form = form

        auto_submitted = request.POST.get(constants.timeout_happened)

        # if the page doesn't have a timeout_seconds, only the timeoutworker
        # should be able to auto-submit it.
        # otherwise users could append timeout_happened to the URL to skip pages
        has_secret_code = (
            request.POST.get(constants.admin_secret_code) == ADMIN_SECRET_CODE)

        # todo: make sure users can't change the result by removing 'timeout_happened'
        # from URL
        if auto_submitted and (has_secret_code or self.has_timeout()):
            self.timeout_happened = True  # for public API
            self._process_auto_submitted_form(form)
        else:
            self.timeout_happened = False
            is_bot = self.participant._is_bot
            if form.is_valid():
                if is_bot and post_data.get('must_fail'):
                    raise BotError(
                        'Page "{}": Bot tried to submit intentionally invalid '
                        'data with '
                        'SubmissionMustFail, but it passed validation anyway:'
                        ' {}.'.format(
                            self.__class__.__name__,
                            bot_prettify_post_data(post_data)))
                # assigning to self.object is not really necessary
                self.object = form.save()
            else:
                if is_bot and not post_data.get('must_fail'):

                    errors = [
                        "{}: {}".format(k, repr(v))
                        for k, v in form.errors.items()]
                    raise BotError(
                        'Page "{}": Bot submission failed form validation: {} '
                        'Check your bot in tests.py, '
                        'then create a new session. '
                        'Data submitted was: {}'.format(
                            self.__class__.__name__,
                            errors,
                            bot_prettify_post_data(post_data),
                        ))
                return self.form_invalid(form)
        self.before_next_page()
        if self.session.use_browser_bots:
            if self._index_in_pages == self.participant._max_page_index:
                bot = EphemeralBrowserBot(self)
                try:
                    bot.prepare_next_submit(html='')
                    submission = bot.get_next_post_data()
                except StopIteration:
                    bot.send_completion_message()
                    return HttpResponse('Bot completed')
                else:
                    raise BotError(
                        'Finished the last page, '
                        'but the bot is still trying '
                        'to submit more data ({}).'.format(submission)
                    )
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
        for field_name in self.get_form_fields():
            if field_name not in timeout_submission:
                # get default value for datatype if the user didn't specify
                ModelField = self.form_model._meta.get_field_by_name(
                    field_name
                )[0]
                # TODO: should we warn if the attribute doesn't exist?
                value = getattr(ModelField, 'auto_submit_default', None)
                timeout_submission[field_name] = value
        return timeout_submission

    def _process_auto_submitted_form(self, form):
        '''
        # an empty submitted form looks like this:
        # {'f_currency': None, 'f_bool': None, 'f_int': None, 'f_char': ''}
        '''
        auto_submit_values = self._get_auto_submit_values()

        # force the form to be cleaned
        form.is_valid()

        has_non_field_error = form.errors.pop('__all__', False)

        # In a non-timeout form, error_message is only run if there are no
        # field errors (because the error_message function assumes all fields exist)
        # however, if there is a timeout, we accept the form even if there are some field errors,
        # so we have to make sure we don't skip calling error_message()
        if form.errors and not has_non_field_error:
            if hasattr(self, 'error_message'):
                try:
                    has_non_field_error = bool(self.error_message(form.cleaned_data))
                except:
                    has_non_field_error = True

        if has_non_field_error:
            # non-field errors exist.
            # ignore form, use timeout_submission entirely
            auto_submit_values_to_use = auto_submit_values
        elif form.errors:
            auto_submit_values_to_use = {}
            for field_name in form.errors:
                auto_submit_values_to_use[field_name] = auto_submit_values[field_name]
            form.errors.clear()
            form.save()
        else:
            auto_submit_values_to_use = {}
            form.save()
        for field_name in auto_submit_values_to_use:
            setattr(self.object, field_name, auto_submit_values_to_use[field_name])

    def has_timeout(self):
        return PageTimeout.objects.filter(
            participant=self.participant,
            page_index=self.participant._index_in_pages).exists()

    _remaining_timeout_seconds = 'unset'
    def remaining_timeout_seconds(self):

        if self._remaining_timeout_seconds is not 'unset':
            return self._remaining_timeout_seconds

        timeout_seconds = self.get_timeout_seconds()
        if timeout_seconds is None:
            # don't hit the DB at all
            pass
        else:
            current_time = time.time()
            expiration_time = current_time + timeout_seconds

            timeout_object, created = PageTimeout.objects.get_or_create(
                participant=self.participant,
                page_index=self.participant._index_in_pages,
                defaults={'expiration_time': expiration_time})

            timeout_seconds = timeout_object.expiration_time - current_time
            if created and otree.common_internal.USE_REDIS:
                # if using browser bots, don't schedule the timeout,
                # because if it's a short timeout, it could happen before
                # the browser bot submits the page. Because the timeout
                # doesn't query the botworker (it is distinguished from bot
                # submits by the timeout_happened flag), it will "skip ahead"
                # and therefore confuse the bot system.
                if not self.session.use_browser_bots:
                    otree.timeout.tasks.submit_expired_url.schedule(
                        (
                            self.participant.code,
                            self.request.path,
                        ),
                        # add some seconds to account for latency of request + response
                        # this will (almost) ensure
                        # (1) that the page will be submitted by JS before the
                        # timeoutworker, which ensures that self.request.POST
                        # actually contains a value.
                        # (2) that the timeoutworker doesn't accumulate a lead
                        # ahead of the real page, which could result in being >1
                        # page ahead. that means that entire pages could be skipped

                        # task queue can't schedule tasks in the past
                        # at least 1 second from now
                        delay=max(1, timeout_seconds+8))
        self._remaining_timeout_seconds = timeout_seconds
        return timeout_seconds

    def get_timeout_seconds(self):
        return self.timeout_seconds

    timeout_seconds = None
    timeout_submission = None
    timer_text = ugettext_lazy("Time left to complete this page:")

    def set_extra_attributes(self):
        pass


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

    # Translators: the default title of a wait page
    title_text = ugettext_lazy('Please wait')
    body_text = None

    def _get_default_body_text(self):
        '''
        needs to be a method because it could say
        "waiting for the other player", "waiting for the other players"...
        '''
        return ''

    def get_context_data(self, **kwargs):
        title_text = self.title_text
        body_text = self.body_text

        # could evaluate to false like 0
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


class PlayerUpdateView(FormPageMixin, FormPageOrInGameWaitPageMixin,
                       vanilla.UpdateView):

    def get_object(self):
        Cls = self.form_model
        if Cls == self.GroupClass:
            return self.group
        if Cls == self.PlayerClass:
            return self.player
        if Cls == UndefinedFormModel:
            return UndefinedFormModel.objects.all()[0]


class InGameWaitPage(FormPageOrInGameWaitPageMixin, InGameWaitPageMixin,
                     GenericWaitPageMixin, vanilla.UpdateView):
    """public API wait page

    """
    pass


class GetFloppyFormClassMixin(object):
    def get_form_class(self):
        """A drop-in replacement for
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
        print('****************in server process')
        print([s.code for s in models.Session.objects.all()])
        self.session = get_object_or_404(
            otree.models.Session, code=session_code)
        return super(AdminSessionPageMixin, self).dispatch(
            request, *args, **kwargs)
