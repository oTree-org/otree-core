import itertools
import time
import django.test
from six.moves import range
from six.moves import zip

from otree import constants_internal
import otree.common_internal
from otree.common_internal import id_label_name

from otree.common import Currency as c
from otree.db import models
from otree.models_concrete import ParticipantToPlayerLookup
from otree.models.session import Session
from otree.models.varsmixin import ModelWithVars


class Participant(ModelWithVars):

    class Meta:
        ordering = ['pk']
        app_label = "otree"
        index_together = ['session', 'mturk_worker_id', 'mturk_assignment_id']

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
    mturk_assignment_id = models.CharField(
        max_length=50, null=True)
    mturk_worker_id = models.CharField(max_length=50, null=True)
    mturk_reward_paid = models.BooleanField(default=False)
    mturk_bonus_paid = models.BooleanField(default=False)

    start_order = models.PositiveIntegerField(db_index=True)

    # unique=True can't be set, because the same external ID could be reused
    # in multiple sequences. however, it should be unique within the sequence.
    label = models.CharField(
        max_length=50, null=True, doc=(
            "Label assigned by the experimenter. Can be assigned by passing a "
            "GET param called 'participant_label' to the participant's start "
            "URL"
        )
    )

    _index_in_subsessions = models.PositiveIntegerField(default=0, null=True)

    _index_in_pages = models.PositiveIntegerField(default=0, db_index=True)

    id_in_session = models.PositiveIntegerField(null=True)

    def _id_in_session(self):
        """the human-readable version."""
        return 'P{}'.format(self.id_in_session)

    _waiting_for_ids = models.CharField(null=True, max_length=300)

    code = models.RandomCharField(
        length=8, db_index=True,
        doc=(
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
        default=False, db_index=True,
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

    _is_auto_playing = models.BooleanField(default=False)

    def _start_auto_play(self):
        self._is_auto_playing = True
        self.save()

        client = django.test.Client()

        if not self.visited:
            client.get(self._start_url(), follow=True)

    def _stop_auto_play(self):
        self._is_auto_playing = False
        self.save()

    def _current_page(self):
        return '{}/{} pages'.format(
            self._index_in_pages, self._max_page_index
        )

    def get_players(self):
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
        for player in self.get_players():
            app_name = player._meta.app_config.name
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

    def build_participant_to_player_lookups(self, num_pages_in_each_app):

        def pages_for_player(player):
            return num_pages_in_each_app[player._meta.app_config.name]

        indexes = itertools.count()

        ParticipantToPlayerLookup.objects.bulk_create([
            ParticipantToPlayerLookup(
                participant_pk=self.pk,
                page_index=page_index,
                app_name=player._meta.app_config.name,
                player_pk=player.pk,
            )
            for player in self.get_players()
            for _, page_index in zip(
                range(pages_for_player(player) + 1),
                indexes
            )
            # +1 is for WaitUntilAssigned...
        ])

        self._max_page_index = next(indexes) - 1
        self.save()

    def __unicode__(self):
        return self.name()

    def _start_url(self):
        return '/InitializeParticipant/{}'.format(self.code)

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

    def name(self):
        return id_label_name(self.pk, self.label)
