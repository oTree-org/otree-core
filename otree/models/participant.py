import datetime
import time

from sqlalchemy import Column as Column, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import sqltypes as st
from starlette.exceptions import HTTPException
import otree.common
import otree.database
from otree.common import random_chars_8, ADMIN_SECRET_CODE
import otree.constants
from otree.database import MixinVars, CurrencyType
from otree.lookup import url_i_should_be_on, get_page_lookup
import otree.channels.utils as channel_utils
from otree import settings


class Participant(MixinVars, otree.database.SSPPGModel):
    __tablename__ = 'otree_participant'

    session_id = Column(st.Integer, ForeignKey('otree_session.id', ondelete='CASCADE'))
    # getting integrityerror, so trying passive_deletes
    # https://stackoverflow.com/questions/5033547/sqlalchemy-cascade-delete
    session = relationship("Session", back_populates="pp_set")

    label = Column(st.String(100), nullable=True)

    id_in_session = Column(st.Integer, nullable=True)

    payoff = Column(CurrencyType, default=0)

    # better to use a string so that it doesn't become unofficial API
    time_started_utc = Column(st.String(50), nullable=True)
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
        index=True,
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

    _SETATTR_NO_FIELD_HINT = ' You can define it in the PARTICIPANT_FIELDS setting.'

    _is_bot = Column(st.Boolean, default=False)
    # can't start with an underscore because used in template
    # can't end with underscore because it's a django field (fields.E001)
    is_browser_bot = Column(st.Boolean, default=False)

    _timeout_expiration_time = otree.database.FloatField()
    _timeout_page_index = Column(st.Integer,)

    _gbat_is_connected = Column(st.Boolean, default=False)
    _gbat_tab_hidden = Column(st.Boolean, default=False)
    _gbat_page_index = Column(st.Integer,)
    _gbat_grouped = Column(st.Boolean,)

    def set_label(self, label):
        if not label:
            return
        if len(label) > 100:
            raise HTTPException(
                404, f'participant_label is too long or malformed: {label}'
            )
        self.label = label

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
            if not pp.label:
                pp.set_label(participant_label)

            # use UTC because daylight savings is not abandoned yet in EU
            # if anything, they will switch to permanent CEST (UTC+2)
            pp.time_started_utc = str(datetime.datetime.utcnow())
            pp._last_page_timestamp = int(time.time())

            from otree import common2

            row = common2.TimeSpentRow(
                session_code=pp._session_code,
                participant_id_in_session=pp.id_in_session,
                participant_code=pp.code,
                page_index=0,
                app_name='',
                page_name='InitializeParticipant',
                epoch_time_completed=int(time.time()),
                round_number=1,
                timeout_happened=0,
                is_wait_page=0,
            )
            common2.write_row_to_page_buffer(row)

    def _update_monitor_table(self):
        from otree import export

        channel_utils.sync_group_send(
            group=channel_utils.session_monitor_group_name(self._session_code),
            data=dict(rows=export.get_rows_for_monitor([self])),
        )

    def _get_page_instance(self):
        if self._index_in_pages > self._max_page_index:
            return
        page = get_page_lookup(
            self._session_code, self._index_in_pages
        ).page_class.instantiate_without_request()
        page.set_attributes(self)
        return page

    def _submit_current_page(self):
        from otree.api import Page

        page = self._get_page_instance()
        if isinstance(page, Page):
            from starlette.datastructures import FormData

            page._form_data = FormData(
                {
                    otree.constants.admin_secret_code: ADMIN_SECRET_CODE,
                    otree.constants.timeout_happened: '1',
                }
            )
            page.post()

    def _visit_current_page(self):
        """
        we need the redirect logic because if it's from ensure_pages_visited,
        then the previous page
        was a wait page, so that will not handle redirects.
        """
        # don't need to handle more redirects than that.
        for i in range(5):
            page = self._get_page_instance()
            if not page:
                return
            # it's possible that the slowest user is on a wait page,
            # especially if their browser is closed.
            # because they were waiting for another user who then
            # advanced past the wait page, but they were never
            # advanced themselves.
            resp = page.get()
            if not str(resp.status_code).startswith('3'):
                return

    def _get_finished(self):
        return self.vars.get('finished', False)
