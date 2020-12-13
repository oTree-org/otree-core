import datetime
from time import time
import otree.common
import otree.database
from otree.common import random_chars_8
from otree.lookup import url_i_should_be_on, get_page_lookup
from otree.database import db, MixinVars, CurrencyType
from sqlalchemy.orm import relationship
from sqlalchemy import Column as Column, ForeignKey
from sqlalchemy.sql import sqltypes as st
from sqlalchemy.ext.declarative import declarative_base, declared_attr


class Participant(otree.database.SSPPGModel, MixinVars):
    __tablename__ = 'otree_participant'

    session_id = Column(st.Integer, ForeignKey('otree_session.id'))
    session = relationship("Session", back_populates="pp_set")

    label = Column(st.String(50), nullable=True,)

    id_in_session = Column(st.Integer, nullable=True)

    payoff = Column(CurrencyType, default=0)

    time_started = Column(st.DateTime, nullable=True)
    mturk_assignment_id = Column(st.String(50), nullable=True)
    mturk_worker_id = Column(st.String(50), nullable=True)

    _index_in_pages = Column(st.Integer, default=0, index=True)

    def _numeric_label(self):
        """the human-readable version."""
        return 'P{}'.format(self.id_in_session)

    _monitor_note = Column(st.String(300), nullable=True)

    code = Column(
        st.String(16),
        default=random_chars_8,
        # set non-nullable, until we make our CharField non-nullable
        nullable=False,
        # unique implies DB index
        unique=True,
    )

    # useful when we don't want to load the whole session just to get the code
    _session_code = Column(st.String(16))

    visited = Column(st.Boolean, default=False, index=True,)

    # stores when the page was first visited
    _last_page_timestamp = Column(st.Integer, nullable=True)

    _last_request_timestamp = Column(st.Integer, nullable=True)

    is_on_wait_page = Column(st.Boolean, default=False)

    # these are both for the admin
    # In the changelist, simply call these "page" and "app"
    _current_page_name = Column(st.String(200), nullable=True)
    _current_app_name = Column(st.String(200), nullable=True)

    # only to be displayed in the admin participants changelist
    _round_number = Column(st.Integer, nullable=True)

    _current_form_page_url = Column(st.String(500))

    _max_page_index = Column(st.Integer,)

    _is_bot = Column(st.Boolean, default=False)
    # can't start with an underscore because used in template
    # can't end with underscore because it's a django field (fields.E001)
    is_browser_bot = Column(st.Boolean, default=False)

    _timeout_expiration_time = otree.database.FloatField()
    _timeout_page_index = Column(st.Integer,)

    _gbat_is_waiting = Column(st.Boolean, default=False)
    _gbat_page_index = Column(st.Integer,)
    _gbat_grouped = Column(st.Boolean,)

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
            players = models_module.Player.objects_filter(participant=self).order_by(
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
        return '/OutOfRangeNotification/' + self.code

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
        return PlayerClass.objects_get(
            participant=self, round_number=lookup.round_number
        )

    def initialize(self, participant_label):
        """in a separate function so that we can call it individually,
        e.g. from advance_last_place_participants"""
        pp = self
        if pp._index_in_pages == 0:
            pp._index_in_pages = 1
            pp.visited = True

            # participant.label might already have been set
            pp.label = pp.label or participant_label

            # default to Central European Time
            pp.time_started = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            pp._last_page_timestamp = time()
            player = pp._get_current_player()
            player.start()
