from sqlalchemy import Column as C, ForeignKey
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import sqltypes as st

import otree.database
from otree.common import (
    get_models_module,
    in_round,
    in_rounds,
    InvalidRoundError,
    get_constants,
)
from otree.constants import BaseConstants, get_role, get_roles
from otree.database import db, NoResultFound, MixinSessionFK, SPGModel


class BaseGroup(SPGModel, MixinSessionFK):
    __abstract__ = True

    id_in_subsession = C(st.Integer, index=True)

    round_number = C(st.Integer, index=True)

    @property
    def _Constants(self) -> BaseConstants:
        return get_constants(self.get_folder_name())

    def get_players(self):
        return list(self.player_set.order_by('id_in_group'))

    def get_player_by_id(self, id_in_group):
        try:
            return self.player_set.filter_by(id_in_group=id_in_group).one()
        except NoResultFound:
            msg = 'No player with id_in_group {}'.format(id_in_group)
            raise ValueError(msg) from None

    def get_player_by_role(self, role):
        if get_roles(self._Constants):
            try:
                return self.player_set.filter_by(_role=role).one()
            except NoResultFound:
                pass
        else:
            for p in self.get_players():
                if p.role() == role:
                    return p
        msg = f'No player with role "{role}"'
        raise ValueError(msg)

    def set_players(self, players_list):
        """
        don't allow passing in a list of ints, because there are 2 ways of reading it.
        Does set_players([2,3,1]) mean that player 1 gets id_in_group 2,
        or does it mean player 2 gets id_in_group 1?
        """
        Constants = self._Constants
        roles = get_roles(Constants)
        for i, player in enumerate(players_list, start=1):
            player.group = self
            player.id_in_group = i
            player._role = get_role(roles, i)
        db.commit()

    def in_round(self, round_number):
        try:
            return in_round(
                type(self),
                round_number,
                session=self.session,
                id_in_subsession=self.id_in_subsession,
            )
        except InvalidRoundError as exc:
            msg = (
                str(exc)
                + '; '
                + (
                    'Hint: you should not use this '
                    'method if you are rearranging groups between rounds.'
                )
            )
            ExceptionClass = type(exc)
            raise ExceptionClass(msg) from None

    def in_rounds(self, first, last):
        try:
            return in_rounds(
                type(self),
                first,
                last,
                session=self.session,
                id_in_subsession=self.id_in_subsession,
            )
        except InvalidRoundError as exc:
            msg = (
                str(exc)
                + '; '
                + (
                    'Hint: you should not use this '
                    'method if you are rearranging groups between rounds.'
                )
            )
            ExceptionClass = type(exc)
            raise ExceptionClass(msg) from None

    def in_previous_rounds(self):
        return self.in_rounds(1, self.round_number - 1)

    def in_all_rounds(self):
        return self.in_previous_rounds() + [self]

    @declared_attr
    def subsession_id(cls):
        app_name = cls.get_folder_name()
        return C(
            st.Integer, ForeignKey(f'{app_name}_subsession.id', ondelete='CASCADE')
        )

    @declared_attr
    def subsession(cls):
        return relationship(f'{cls.__module__}.Subsession', back_populates='group_set')

    @declared_attr
    def player_set(cls):
        return relationship(
            f'{cls.__module__}.Player', back_populates="group", lazy='dynamic'
        )
