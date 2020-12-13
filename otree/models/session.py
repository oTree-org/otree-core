import logging
import time
from otree.templating import get_template_name_if_exists
from otree.templating.loader import TemplateLoadError
from otree import settings
from sqlalchemy.orm import relationship
import otree.common
import otree.constants
from otree.database import NoResultFound, MixinVars, session_scope
import otree.database
from otree.channels.utils import auto_advance_group
from otree.common import (
    random_chars_8,
    random_chars_10,
    get_admin_secret_code,
    get_app_label_from_name,
)


from otree.models_concrete import RoomToSession
from sqlalchemy import Column
from sqlalchemy.sql import sqltypes as st

logger = logging.getLogger('otree')


ADMIN_SECRET_CODE = get_admin_secret_code()


class Session(otree.database.SSPPGModel, MixinVars):
    __tablename__ = 'otree_session'

    config: dict = Column(otree.database._PickleField, default=dict)

    pp_set = relationship("Participant", back_populates="session", lazy='dynamic')
    # label of this session instance
    label = Column(st.String, nullable=True)

    code = Column(st.String(16), default=random_chars_8, nullable=False, unique=True,)

    mturk_HITId = Column(st.String(300), nullable=True)
    mturk_HITGroupId = Column(st.String(300), nullable=True)

    is_mturk = Column(st.Boolean, default=False)

    def mturk_num_workers(self):
        assert self.is_mturk
        return int(self.num_participants / settings.MTURK_NUM_PARTICIPANTS_MULTIPLE)

    mturk_use_sandbox = Column(st.Boolean, default=True)

    # use Float instead of DateTime because DateTime
    # is a pain to work with (e.g. naive vs aware datetime objects)
    # and there is no need here for DateTime
    mturk_expiration = Column(st.Float, nullable=True)
    mturk_qual_id = Column(st.String(50), default='')

    archived = Column(st.Boolean, default=False, index=True,)

    comment = Column(st.Text)

    _anonymous_code = Column(
        st.String(20), default=random_chars_10, nullable=False, index=True,
    )

    is_demo = Column(st.Boolean, default=False)

    _admin_report_app_names = Column(st.Text, default='')
    _admin_report_num_rounds = Column(st.String(255), default='')

    num_participants = Column(st.Integer)

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
    def use_browser_bots(self):
        return self.config.get('use_browser_bots', False)

    def mock_exogenous_data(self):
        '''
        It's for any exogenous data:
        - participant labels (which are not passed in through REST API)
        - participant vars
        - session vars (if we enable that)
        '''
        if self.config.get('mock_exogenous_data'):
            import shared_out as user_utils

            user_utils.mock_exogenous_data(self)

    def get_subsessions(self):
        lst = []
        app_sequence = self.config['app_sequence']
        for app in app_sequence:
            models_module = otree.common.get_models_module(app)
            subsessions = models_module.Subsession.objects_filter(
                session=self
            ).order_by('round_number')
            lst.extend(list(subsessions))
        return lst

    def get_participants(self):
        return list(self.pp_set.order_by('id_in_session'))

    def mturk_worker_url(self):
        # different HITs
        # get the same preview page, because they are lumped into the same
        # "hit group". This is not documented, but it seems HITs are lumped
        # if a certain subset of properties are the same:
        # https://forums.aws.amazon.com/message.jspa?messageID=597622#597622
        # this seems like the correct design; the only case where this will
        # not work is if the HIT was deleted from the server, but in that case,
        # the HIT itself should be canceled.

        # 2018-06-04:
        # the format seems to have changed to this:
        # https://worker.mturk.com/projects/{group_id}/tasks?ref=w_pl_prvw
        # but the old format still works.
        # it seems I can't replace groupId by hitID, which i would like to do
        # because it's more precise.
        subdomain = "workersandbox" if self.mturk_use_sandbox else 'www'
        return "https://{}.mturk.com/mturk/preview?groupId={}".format(
            subdomain, self.mturk_HITGroupId
        )

    def mturk_is_expired(self):
        # self.mturk_expiration is offset-aware, so therefore we must compare
        # it against an offset-aware value.
        return self.mturk_expiration and self.mturk_expiration < time.time()

    def mturk_is_active(self):

        return self.mturk_HITId and not self.mturk_is_expired()

    def advance_last_place_participants(self):
        """the problem with using the test client to make get/post requests is
        (1) this request already has the global asyncio.lock
        (2) there are apparently some issues with async/await and event loops.
        """
        from otree.lookup import get_page_lookup
        from otree.api import WaitPage, Page

        participants = self.get_participants()

        # in case some participants haven't started
        unvisited_participants = False
        for p in participants:
            if p._index_in_pages == 0:
                p.initialize(None)

        if unvisited_participants:
            # that's it -- just visit the start URL, advancing by 1
            return

        last_place_page_index = min([p._index_in_pages for p in participants])
        last_place_participants = [
            p for p in participants if p._index_in_pages == last_place_page_index
        ]
        for p in last_place_participants:
            page_index = p._index_in_pages
            if page_index >= p._max_page_index:
                return
            page = get_page_lookup(
                self.code, page_index
            ).page_class.instantiate_without_request()
            page.set_attributes(p)

            if isinstance(page, Page):

                from starlette.datastructures import FormData

                page._is_frozen = False
                page._form_data = FormData(
                    {
                        otree.constants.admin_secret_code: ADMIN_SECRET_CODE,
                        otree.constants.timeout_happened: '1',
                    }
                )
                # TODO: should we also call .get() so that _update_monitor_table will also get run?
                resp = page.post()
                if resp.status_code >= 400:
                    msg = (
                        f'Submitting page {p._current_form_page_url} failed, '
                        f'returned HTTP status code {resp.status_code}. '
                        'Check the logs'
                    )
                    raise AssertionError(msg)
            else:
                # it's possible that the slowest user is on a wait page,
                # especially if their browser is closed.
                # because they were waiting for another user who then
                # advanced past the wait page, but they were never
                # advanced themselves.
                resp = page.inner_dispatch(request=None)

            # do the auto-advancing here,
            # rather than in increment_index_in_pages,
            # because it's only needed here.
            otree.channels.utils.sync_group_send(
                group=auto_advance_group(p.code), data={'auto_advanced': True}
            )

    def get_room(self):
        from otree.room import ROOM_DICT

        try:
            room_name = RoomToSession.objects_get(session=self).room_name
            return ROOM_DICT[room_name]
        except NoResultFound:
            return None

    def _get_payoff_plus_participation_fee(self, payoff):
        '''For a participant who has the given payoff,
        return their payoff_plus_participation_fee
        Useful to define it here, for data export
        '''

        return self.config['participation_fee'] + payoff.to_real_world_currency(self)

    def _set_admin_report_app_names(self):

        admin_report_app_names = []
        num_rounds_list = []
        for app_name in self.config['app_sequence']:
            models_module = otree.common.get_models_module(app_name)
            app_label = get_app_label_from_name(app_name)
            try:
                get_template_name_if_exists(
                    [f'{app_label}/admin_report.html', f'{app_label}/AdminReport.html']
                )
            except TemplateLoadError:
                pass
            else:
                admin_report_app_names.append(app_name)
                num_rounds_list.append(models_module.Constants.num_rounds)

        self._admin_report_app_names = ';'.join(admin_report_app_names)
        self._admin_report_num_rounds = ';'.join(str(n) for n in num_rounds_list)

    def _admin_report_apps(self):
        return self._admin_report_app_names.split(';')

    def _admin_report_num_rounds_list(self):
        return [int(num) for num in self._admin_report_num_rounds.split(';')]

    def has_admin_report(self):
        return bool(self._admin_report_app_names)
