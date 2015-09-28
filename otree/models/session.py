import copy
import itertools
import time

import django.test

from otree import constants_internal
import otree.common_internal
from otree.common_internal import id_label_name

from otree.common import Currency as c
from otree.db import models
from otree.models_concrete import SessionuserToUserLookup


class GlobalSingleton(models.Model):
    """object that can hold site-wide settings. There should only be one
    GlobalSingleton object. Also used for wait page actions.
    """

    class Meta:
        app_label = "otree"

    default_session = models.ForeignKey('Session', null=True, blank=True)
    admin_access_code = models.RandomCharField(
        length=8, doc=('used for authentication to things only the '
                       'admin/experimenter should access')
    )


class ModelWithVars(models.Model):
    vars = models.JSONField(default=dict)

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(ModelWithVars, self).__init__(*args, **kwargs)
        self._old_vars = copy.deepcopy(self.vars)

    def save(self, *args, **kwargs):
        # Trick otree_save_the_change to update vars
        if hasattr(self, '_changed_fields') and self.vars != self._old_vars:
            self._changed_fields['vars'] = self._old_vars
        super(ModelWithVars, self).save(*args, **kwargs)


# for now removing SaveTheChange
class Session(ModelWithVars):

    class Meta:
        # if i don't set this, it could be in an unpredictable order
        ordering = ['pk']
        app_label = "otree"

    config = models.JSONField(
        default=dict, null=True,
        doc=("the session config dict, as defined in the "
             "programmer's settings.py."))

    # label of this session instance
    label = models.CharField(
        max_length=300, null=True, blank=True,
        help_text='For internal record-keeping')

    experimenter_name = models.CharField(
        max_length=300, null=True, blank=True,
        help_text='For internal record-keeping')

    code = models.RandomCharField(
        length=8, doc="Randomly generated unique identifier for the session.")

    time_scheduled = models.DateTimeField(
        null=True, doc="The time at which the session is scheduled",
        help_text='For internal record-keeping', blank=True)

    time_started = models.DateTimeField(
        null=True,
        doc="The time at which the experimenter started the session")

    mturk_HITId = models.CharField(
        max_length=300, null=True, blank=True,
        help_text='Hit id for this session on MTurk')
    mturk_HITGroupId = models.CharField(
        max_length=300, null=True, blank=True,
        help_text='Hit id for this session on MTurk')
    mturk_qualification_type_id = models.CharField(
        max_length=300, null=True, blank=True,
        help_text='Qualification type that is '
                  'assigned to each worker taking hit')

    # since workers can drop out number of participants on server should be
    # greater than number of participants on mturk
    # value -1 indicates that this session it not intended to run on mturk
    mturk_num_participants = models.IntegerField(
        default=-1,
        help_text="Number of participants on MTurk")

    mturk_sandbox = models.BooleanField(
        default=True,
        help_text="Should this session be created in mturk sandbox?")

    archived = models.BooleanField(
        default=False,
        doc=("If set to True the session won't be visible on the "
             "main ViewList for sessions"))

    git_commit_timestamp = models.CharField(
        max_length=200, null=True,
        doc=(
            "Indicates the version of the code (as recorded by Git) that was "
            "used to run the session, so that the session can be replicated "
            "later.\n Search through the Git commit log to find a commit that "
            "was made at this time."))

    comment = models.TextField(blank=True)

    _ready_to_play = models.BooleanField(default=False)

    _anonymous_code = models.RandomCharField(length=10)

    special_category = models.CharField(
        max_length=20, null=True,
        doc="whether it's a test session, demo session, etc.")

    # whether someone already viewed this session's demo links
    demo_already_used = models.BooleanField(default=False)

    # indicates whether a session has been fully created (not only has the
    # model itself been created, but also the other models in the hierarchy)
    ready = models.BooleanField(default=False)

    _pre_create_id = models.CharField(max_length=300, null=True)

    def __unicode__(self):
        return self.code

    @property
    def participation_fee(self):
        '''This method is deprecated from public API,
        but still useful internally (like data export)'''
        return self.config['participation_fee']

    @property
    def real_world_currency_per_point(self):
        '''This method is deprecated from public API,
        but still useful internally (like data export)'''
        return self.config['real_world_currency_per_point']

    @property
    def session_type(self):
        '''2015-07-10: session_type is deprecated
        this shim method will be removed eventually'''
        return self.config

    def is_open(self):
        return GlobalSingleton.objects.get().default_session == self

    def is_for_mturk(self):
        return (not self.is_demo()) and (self.mturk_num_participants > 0)

    def is_demo(self):
        return (
            self.special_category ==
            constants_internal.session_special_category_demo
        )

    def subsession_names(self):
        names = []
        for subsession in self.get_subsessions():
            app_name = subsession._meta.app_config.name
            name = '{} {}'.format(
                otree.common_internal.app_name_format(app_name),
                subsession.name()
            )
            names.append(name)
        if names:
            return ', '.join(names)
        else:
            return '[empty sequence]'

    def get_subsessions(self):
        lst = []
        app_sequence = self.config['app_sequence']
        for app in app_sequence:
            models_module = otree.common_internal.get_models_module(app)
            subsessions = models_module.Subsession.objects.filter(
                session=self
            ).order_by('round_number')
            lst.extend(list(subsessions))
        return lst

    def delete(self, using=None):
        for subsession in self.get_subsessions():
            subsession.delete()
        super(Session, self).delete(using)

    def get_participants(self):
        return self.participant_set.all()

    def payments_ready(self):
        for participants in self.get_participants():
            if not participants.payoff_is_complete():
                return False
        return True
    payments_ready.boolean = True

    def _create_groups_and_initialize(self):
        # if ppg is None, then the arrival time doesn't matter because
        # everyone is assigned to one big group.
        # otherwise, even in single-player games, you would have to wait
        # for other players to arrive
        # the drawback of this approach is that id_in_group is
        # predetermined, rather than by arrival time.
        # alternative design:
        # instead of checking ppg, we could also check if the game
        # contains a wait page
        # another alternative:
        # allow players to start even if the rest of the group hasn't arrived
        # but this might break some assumptions such as len(grp.get_players())
        # also, what happens if you get to the next round before
        # another player has started the first? you can't clone the
        # previous round's groups
        for subsession in self.get_subsessions():
            cond = (
                self.config.get('group_by_arrival_time') and
                subsession._Constants.players_per_group is not None
            )
            if cond:
                if subsession.round_number == 1:
                    subsession._set_players_per_group_list()
                subsession._create_empty_groups()
            else:
                subsession._create_groups()
            subsession._initialize()
            subsession.save()
        self._ready_to_play = True
        # assert self is subsession.session
        self.save()

    def mturk_requester_url(self):
        if self.mturk_sandbox:
            requester_url = (
                "https://requestersandbox.mturk.com/mturk/manageHITs"
            )
        else:
            requester_url = "https://requester.mturk.com/mturk/manageHITs"
        return requester_url

    def mturk_worker_url(self):
        if self.mturk_sandbox:
            worker_url = (
                "https://workersandbox.mturk.com/mturk/preview?groupId={}"
            ).format(self.mturk_HITGroupId)
        else:
            worker_url = (
                "https://www.mturk.com/mturk/preview?groupId={}"
            ).format(self.mturk_HITGroupId)
        return worker_url

    def advance_last_place_participants(self):
        participants = self.get_participants()

        c = django.test.Client()

        # in case some participants haven't started
        some_participants_not_visited = False
        for p in participants:
            if not p.visited:
                some_participants_not_visited = True
                c.get(p._start_url(), follow=True)

        if some_participants_not_visited:
            # refresh from DB so that _current_form_page_url gets set
            participants = self.participant_set.all()

        last_place_page_index = min([p._index_in_pages for p in participants])
        last_place_participants = [
            p for p in participants
            if p._index_in_pages == last_place_page_index
        ]

        for p in last_place_participants:
            # what if current_form_page_url hasn't been set yet?
            resp = c.post(
                p._current_form_page_url,
                data={constants_internal.auto_submit: True}, follow=True
            )
            assert resp.status_code < 400

    def build_session_user_to_user_lookups(self):
        subsession_app_names = self.config['app_sequence']

        num_pages_in_each_app = {}
        for app_name in subsession_app_names:
            views_module = otree.common_internal.get_views_module(app_name)

            num_pages = len(views_module.page_sequence)
            num_pages_in_each_app[app_name] = num_pages

        for participant in self.get_participants():
            participant.build_session_user_to_user_lookups(
                num_pages_in_each_app
            )


# for now removing SaveTheChange
class SessionUser(ModelWithVars):

    _index_in_subsessions = models.PositiveIntegerField(default=0, null=True)

    _index_in_pages = models.PositiveIntegerField(default=0)

    id_in_session = models.PositiveIntegerField(null=True)

    def _id_in_session_display(self):
        return 'P{}'.format(self.id_in_session)
    _id_in_session_display.short_description = 'Participant'

    _waiting_for_ids = models.CharField(null=True, max_length=300)

    code = models.RandomCharField(
        length=8, doc=(
            "Randomly generated unique identifier for the participant. If you "
            "would like to merge this dataset with those from another "
            "subsession in the same session, you should join on this field, "
            "which will be the same across subsessions."
        )
    )

    last_request_succeeded = models.BooleanField(
        verbose_name='Health of last server request'
    )

    visited = models.BooleanField(
        default=False,
        doc="""Whether this user's start URL was opened"""
    )

    ip_address = models.GenericIPAddressField(null=True)

    # stores when the page was first visited
    _last_page_timestamp = models.PositiveIntegerField(null=True)

    _last_request_timestamp = models.PositiveIntegerField(null=True)

    is_on_wait_page = models.BooleanField(default=False)

    # these are both for the admin
    # In the changelist, simply call these "page" and "app"
    _current_page_name = models.CharField(max_length=200, null=True,
                                          verbose_name='page')
    _current_app_name = models.CharField(max_length=200, null=True,
                                         verbose_name='app')

    # only to be displayed in the admin participants changelist
    _round_number = models.PositiveIntegerField(
        null=True
    )

    _current_form_page_url = models.URLField()

    _max_page_index = models.PositiveIntegerField()

    def _current_page(self):
        return '{}/{} pages'.format(
            self._index_in_pages, self._max_page_index
        )

    def get_users(self):
        """Used to calculate payoffs"""
        lst = []
        app_sequence = self.session.config['app_sequence']
        for app in app_sequence:
            models_module = otree.common_internal.get_models_module(app)
            players = models_module.Player.objects.filter(
                participant=self
            ).order_by('round_number')
            lst.extend(list(players))
        return lst

    def status(self):
        if not self.visited:
            return 'Not visited yet'

        # check if they are disconnected
        max_seconds_since_last_request = max(
            constants_internal.form_page_poll_interval_seconds,
            constants_internal.wait_page_poll_interval_seconds,
        ) + 10  # for latency
        if self._last_request_timestamp is None:
            # it shouldn't be None, but sometimes is...race condition?
            time_since_last_request = 0
        else:
            time_since_last_request = (
                time.time() - self._last_request_timestamp
            )
        if time_since_last_request > max_seconds_since_last_request:
            return 'Disconnected'
        if self.is_on_wait_page:
            if self._waiting_for_ids:
                return 'Waiting for {}'.format(self._waiting_for_ids)
            return 'Waiting'
        return 'Playing'

    def _pages(self):
        from otree.views.concrete import WaitUntilAssignedToGroup

        pages = []
        for user in self.get_users():
            app_name = user._meta.app_config.name
            views_module = otree.common_internal.get_views_module(app_name)
            subsession_pages = (
                [WaitUntilAssignedToGroup] + views_module.page_sequence
            )
            pages.extend(subsession_pages)
        return pages

    def _pages_as_urls(self):
        return [
            View.url(self, index) for index, View in enumerate(self._pages())
        ]

    def _url_i_should_be_on(self):
        if self._index_in_pages <= self._max_page_index:
            return self._pages_as_urls()[self._index_in_pages]
        else:
            if self.session.mturk_HITId:
                assignment_id = self.mturk_assignment_id
                if self.session.mturk_sandbox:
                    url = (
                        'https://workersandbox.mturk.com/mturk/externalSubmit'
                    )
                else:
                    url = "https://www.mturk.com/mturk/externalSubmit"
                url = otree.common_internal.add_params_to_url(
                    url,
                    {
                        'assignmentId': assignment_id,
                        'extra_param': '1'  # required extra param?
                    }
                )
                return url
            from otree.views.concrete import OutOfRangeNotification
            return OutOfRangeNotification.url(self)

    def build_session_user_to_user_lookups(self, num_pages_in_each_app):

        def pages_for_user(user):
            return num_pages_in_each_app[user._meta.app_config.name]

        indexes = itertools.count()

        SessionuserToUserLookup.objects.bulk_create([
            SessionuserToUserLookup(
                session_user_pk=self.pk,
                page_index=page_index,
                app_name=user._meta.app_config.name,
                user_pk=user.pk,
            )
            for user in self.get_users()
            for _, page_index in zip(range(pages_for_user(user) + 1), indexes)
            # +1 is for WaitUntilAssigned...
        ])

        self._max_page_index = next(indexes) - 1
        self.save()

    class Meta:
        abstract = True


class Participant(SessionUser):

    class Meta:
        ordering = ['pk']
        app_label = "otree"

    exclude_from_data_analysis = models.BooleanField(
        default=False, doc=(
            "if set to 1, the experimenter indicated that this participant's "
            "data points should be excluded from the data analysis (e.g. a "
            "problem took place during the experiment)"
        )
    )

    session = models.ForeignKey(Session)
    time_started = models.DateTimeField(null=True)
    user_type_in_url = constants_internal.user_type_participant
    mturk_assignment_id = models.CharField(max_length=50, null=True)
    mturk_worker_id = models.CharField(max_length=50, null=True)
    mturk_reward_paid = models.BooleanField(default=False)
    mturk_bonus_paid = models.BooleanField(default=False)

    start_order = models.PositiveIntegerField()

    # unique=True can't be set, because the same external ID could be reused
    # in multiple sequences. however, it should be unique within the sequence.
    label = models.CharField(
        max_length=50, null=True, doc=(
            "Label assigned by the experimenter. Can be assigned by passing a "
            "GET param called 'participant_label' to the participant's start "
            "URL"
        )
    )

    def __unicode__(self):
        return self.name()

    def _start_url(self):
        return '/InitializeParticipant/{}'.format(self.code)

    def get_players(self):
        return self.get_users()

    @property
    def payoff(self):
        return sum(player.payoff or c(0) for player in self.get_players())

    def payoff_in_real_world_currency(self):
        return self.payoff.to_real_world_currency(
            self.session
        )

    def payoff_from_subsessions(self):
        """Deprecated on 2015-05-07.
        Remove at some point.
        """
        return self.payoff

    def money_to_pay(self):
        return (
            self.session.config['participation_fee'] +
            self.payoff.to_real_world_currency(self.session)
        )

    def total_pay(self):
        return self.money_to_pay()

    def payoff_is_complete(self):
        return all(p.payoff is not None for p in self.get_players())

    def money_to_pay_display(self):
        complete = self.payoff_is_complete()
        money_to_pay = self.money_to_pay()
        if complete:
            return money_to_pay
        return u'{} (incomplete)'.format(money_to_pay)

    def name(self):
        return id_label_name(self.pk, self.label)
