from django.db import models as djmodels
from django.urls import reverse

import otree.common
from otree.common import random_chars_8
from otree.db import models
from otree.lookup import url_i_should_be_on, get_page_lookup
from otree.db.idmap import ParticipantIDMapMixin

class Participant(models.OTreeModel, models.VarsMixin, ParticipantIDMapMixin):
    class Meta:
        ordering = ['pk']
        app_label = "otree"
        index_together = ['session', 'mturk_worker_id', 'mturk_assignment_id']

    session = djmodels.ForeignKey('otree.Session', on_delete=models.CASCADE)

    vars: dict = models._PickleField(default=dict)
    label = models.CharField(
        max_length=50,
        null=True,
        doc=(
            "Label assigned by the experimenter. Can be assigned by passing a "
            "GET param called 'participant_label' to the participant's start "
            "URL"
        ),
    )

    id_in_session = models.PositiveIntegerField(null=True)

    payoff = models.CurrencyField(default=0)

    time_started = djmodels.DateTimeField(null=True)
    mturk_assignment_id = models.CharField(max_length=50, null=True)
    mturk_worker_id = models.CharField(max_length=50, null=True)

    _index_in_pages = models.PositiveIntegerField(default=0, db_index=True)

    def _numeric_label(self):
        """the human-readable version."""
        return 'P{}'.format(self.id_in_session)

    _monitor_note = models.CharField(null=True, max_length=300)

    code = models.CharField(
        default=random_chars_8,
        max_length=16,
        # set non-nullable, until we make our CharField non-nullable
        null=False,
        # unique implies DB index
        unique=True,
    )

    # useful when we don't want to load the whole session just to get the code
    _session_code = djmodels.CharField(max_length=16)

    visited = models.BooleanField(
        default=False, db_index=True, doc="""Whether this user's start URL was opened"""
    )

    # stores when the page was first visited
    _last_page_timestamp = models.PositiveIntegerField(null=True)

    _last_request_timestamp = models.PositiveIntegerField(null=True)

    is_on_wait_page = models.BooleanField(default=False)

    # these are both for the admin
    # In the changelist, simply call these "page" and "app"
    _current_page_name = models.CharField(
        max_length=200, null=True, verbose_name='page'
    )
    _current_app_name = models.CharField(max_length=200, null=True, verbose_name='app')

    # only to be displayed in the admin participants changelist
    _round_number = models.PositiveIntegerField(null=True)

    _current_form_page_url = djmodels.URLField()

    _max_page_index = models.PositiveIntegerField()

    _is_bot = models.BooleanField(default=False)
    # can't start with an underscore because used in template
    # can't end with underscore because it's a django field (fields.E001)
    is_browser_bot = models.BooleanField(default=False)

    _timeout_expiration_time = models.FloatField()
    _timeout_page_index = models.PositiveIntegerField()

    _gbat_is_waiting = models.BooleanField(default=False)
    _gbat_page_index = models.PositiveIntegerField()
    _gbat_grouped = models.BooleanField()

    def _current_page(self):
        # don't put 'pages' because that causes wrapping which takes more space
        # since it's longer than the header
        return f'{self._index_in_pages}/{self._max_page_index}'

    # because variables used in templates can't start with an underscore
    def current_page_(self):
        return self._current_page()

    def get_players(self):
        """Used to calculate payoffs"""
        lst = []
        app_sequence = self.session.config['app_sequence']
        for app in app_sequence:
            models_module = otree.common.get_models_module(app)
            players = models_module.Player.objects.filter(participant=self).order_by(
                'round_number'
            )
            lst.extend(list(players))
        return lst

    def _url_i_should_be_on(self):
        if not self.visited:
            return self._start_url()
        if self._index_in_pages <= self._max_page_index:
            return url_i_should_be_on(
                self.code, self._session_code, self._index_in_pages
            )
        return reverse('OutOfRangeNotification', args=[self.code])

    def _start_url(self):
        return otree.common.participant_start_url(self.code)

    def payoff_in_real_world_currency(self):
        return self.payoff.to_real_world_currency(self.session)

    def payoff_plus_participation_fee(self):
        return self.session._get_payoff_plus_participation_fee(self.payoff)

    def _get_current_player(self):
        lookup = get_page_lookup(self._session_code, self._index_in_pages)
        models_module = otree.common.get_models_module(lookup.app_name)
        PlayerClass = getattr(models_module, 'Player')
        return PlayerClass.objects.get(
            participant=self, round_number=lookup.round_number
        )
