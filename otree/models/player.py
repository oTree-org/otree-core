import otree.database
from otree.common import in_round, in_rounds

from sqlalchemy.orm import relationship, backref
import sqlalchemy.orm
from sqlalchemy import Column, ForeignKey
from sqlalchemy.sql import sqltypes as st
from otree.database import db, MixinSessionFK, SSPPGModel, CurrencyType
from sqlalchemy.ext.declarative import declared_attr


class BasePlayer(SSPPGModel, MixinSessionFK):
    __abstract__ = True

    id_in_group = Column(st.Integer, nullable=True, index=True,)

    # don't modify this directly! Set player.payoff instead
    _payoff = Column(CurrencyType, default=0)

    round_number = Column(st.Integer, index=True)

    _role = otree.database.StringField()

    # as a property, that means it's overridable
    @property
    def role(self):
        return self._role

    @property
    def payoff(self):
        return self._payoff

    @payoff.setter
    def payoff(self, value):
        if value is None:
            value = 0
        delta = value - self._payoff
        self._payoff += delta
        self.participant.payoff += delta
        # should save it because it may not be obvious that modifying
        # player.payoff also changes a field on a different model
        db.commit()

    @property
    def id_in_subsession(self):
        return self.participant.id_in_session

    # TODO: add back in
    # def __repr__(self):
    #     id_in_subsession = self.id_in_subsession
    #     if id_in_subsession < 10:
    #         # 2 spaces so that it lines up if printing a matrix
    #         fmt_string = '<Player  {}>'
    #     else:
    #         fmt_string = '<Player {}>'
    #     return fmt_string.format(id_in_subsession)

    def in_round(self, round_number):
        return in_round(type(self), round_number, participant=self.participant)

    def in_rounds(self, first, last):
        return in_rounds(type(self), first, last, participant=self.participant)

    def in_previous_rounds(self):
        return self.in_rounds(1, self.round_number - 1)

    def in_all_rounds(self):
        '''i do it this way because it doesn't rely on idmap'''
        return self.in_previous_rounds() + [self]

    def get_others_in_group(self):
        return [p for p in self.group.get_players() if p != self]

    def get_others_in_subsession(self):
        return [p for p in self.subsession.get_players() if p != self]

    def start(self):
        pass

    @declared_attr
    def subsession_id(cls):
        app_name = cls.get_folder_name()
        return Column(st.Integer, ForeignKey(f'{app_name}_subsession.id'))

    @declared_attr
    def subsession(cls):
        return relationship(f'{cls.__module__}.Subsession', back_populates='player_set')

    @declared_attr
    def group_id(cls):
        app_name = cls.get_folder_name()
        # needs to be nullable so re-grouping can happen
        return Column(st.Integer, ForeignKey(f'{app_name}_group.id'), nullable=True)

    @declared_attr
    def group(cls):
        return relationship(f'{cls.__module__}.Group', back_populates='player_set')

    @declared_attr
    def participant_id(cls):
        return Column(st.Integer, ForeignKey('otree_participant.id'))

    @declared_attr
    def participant(cls):
        return relationship("Participant")
