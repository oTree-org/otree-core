import time
from collections import defaultdict
from typing import Iterable
from otree.database import AnyModel, db, MixinSessionFK
from sqlalchemy.orm import relationship
from sqlalchemy import Column, ForeignKey
from sqlalchemy.sql import sqltypes as st

import json


class PageTimeBatch(AnyModel):
    text = Column(st.Text)


class CompletedGroupWaitPage(AnyModel, MixinSessionFK):

    page_index = Column(st.Integer)
    group_id = Column(st.Integer)


class CompletedGBATWaitPage(AnyModel, MixinSessionFK):

    page_index = Column(st.Integer)
    id_in_subsession = Column(st.Integer, default=0)


class CompletedSubsessionWaitPage(AnyModel, MixinSessionFK):

    page_index = Column(st.Integer)


class ParticipantVarsFromREST(AnyModel):

    participant_label = Column(st.String(255))
    room_name = Column(st.String(255))
    _json_data = Column(st.Text)

    @property
    def vars(self):
        return json.loads(self._json_data)

    @vars.setter
    def vars(self, value):
        self._json_data = json.dumps(value)


class RoomToSession(AnyModel, MixinSessionFK):

    room_name = Column(st.String(255), unique=True)


class ChatMessage(AnyModel):

    # the name "channel" here is unrelated to Django channels
    channel = Column(st.String(255))
    participant_id = Column(st.Integer, ForeignKey('otree_participant.id', ondelete='CASCADE'))
    participant = relationship("Participant")
    nickname = Column(st.String(255))

    # call it 'body' instead of 'message' or 'content' because those terms
    # are already used by channels
    body = Column(st.Text)
    timestamp = Column(st.Float, default=time.time)


class TaskQueueMessage(AnyModel):

    method = Column(st.String(50))
    kwargs_json = Column(st.Text)
    epoch_time = Column(st.Integer)

    def kwargs(self) -> dict:
        return json.loads(self.kwargs_json)
