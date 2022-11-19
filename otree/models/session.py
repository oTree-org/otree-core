import logging
import time
from datetime import datetime
from sqlalchemy import Column
from sqlalchemy.orm import relationship
from sqlalchemy.sql import sqltypes as st
from starlette.responses import Response

import otree.common
import otree.constants
import otree.database
from otree import settings
from otree.channels.utils import auto_advance_group
from otree.common import (
    random_chars_8,
    random_chars_join_code,
    get_admin_secret_code,
    get_builtin_constant,
)
from otree.database import NoResultFound, MixinVars
from otree.models_concrete import RoomToSession
from otree.templating import get_template_name_if_exists
from otree.templating.loader import TemplateLoadError


logger = logging.getLogger('otree')


ADMIN_SECRET_CODE = get_admin_secret_code()


class Session(MixinVars, otree.database.SSPPGModel):
    __tablename__ = 'otree_session'

    config: dict = Column(otree.database._PickleField, default=dict)

    # should i also set cascade on all other models?
    # i should check what is deleted.
    pp_set = relationship(
        "Participant",
        back_populates="session",
        lazy='dynamic',
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # label of this session instance
    label = Column(st.String, nullable=True)

    code = Column(
        st.String(16), default=random_chars_8, nullable=False, unique=True, index=True
    )

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

    archived = Column(
        st.Boolean,
        default=False,
        index=True,
    )

    comment = Column(st.Text)

    _anonymous_code = Column(
        st.String(20),
        default=random_chars_join_code,
        nullable=False,
        index=True,
    )

    is_demo = Column(st.Boolean, default=False)

    _admin_report_app_names = Column(st.Text, default='')
    _admin_report_num_rounds = Column(st.String(255), default='')

    num_participants = Column(st.Integer)

    # better to use int because it's portable and no ambiguity
    # about timezone. when you do dt.timestamp() it might give
    # the wrong result if it's in the wrong timezone.
    _created = Column(st.Integer, default=time.time)

    def _created_readable(self):
        now = time.time()
        delta = now - self._created
        days = delta // (24 * 60 * 60)
        if days > 1:
            return f'{days} days ago'
        if days == 1:
            return '1 day ago'
        num_hours = delta // (60 * 60)
        if num_hours >= 1:
            return f'{num_hours} hours ago'
        return '< 1 hour ago'

    _SETATTR_NO_FIELD_HINT = ' You can define it in the SESSION_FIELDS setting.'

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

        participants = self.get_participants()

        last_place_page_index = min([p._index_in_pages for p in participants])
        # max 20 at a time because:
        # - you could run into Heroku 30s timeout.
        # - in a huge session, if your finger slips you could mess up the whole session
        # - less problems with responsiveness, needing to gray out the button, etc.
        # - we could make a confirmation dialog on the client side, but JS less reliable,
        #   slows people down more.
        # this is more proportional to effort.
        last_place_participants = [
            p for p in participants if p._index_in_pages == last_place_page_index
        ][: otree.constants.ADVANCE_SLOWEST_BATCH_SIZE]

        if last_place_page_index == 0:
            for p in last_place_participants:
                p.initialize(None)
                p._visit_current_page()
        else:
            for p in last_place_participants:
                p._submit_current_page()
                # need to do this to update the monitor table, set any timeouts, etc.
                p._visit_current_page()

                # 2020-12-20: this is needed.
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
            try:
                get_template_name_if_exists(
                    [f'{app_name}/admin_report.html', f'{app_name}/AdminReport.html']
                )
            except TemplateLoadError:
                pass
            else:
                admin_report_app_names.append(app_name)
                num_rounds_list.append(get_builtin_constant(app_name, 'num_rounds'))

        self._admin_report_app_names = ';'.join(admin_report_app_names)
        self._admin_report_num_rounds = ';'.join(str(n) for n in num_rounds_list)

    def _admin_report_apps(self):
        return self._admin_report_app_names.split(';')

    def _admin_report_num_rounds_list(self):
        return [int(num) for num in self._admin_report_num_rounds.split(';')]

    def has_admin_report(self):
        return bool(self._admin_report_app_names)
