from sqlalchemy.ext.declarative import declared_attr
import copy
import time
from collections import defaultdict

from sqlalchemy import Column as C, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import sqltypes as st
from sqlalchemy.sql.functions import func


import otree.common
import otree.database
from otree.constants import BaseConstants
from otree.common import (
    get_models_module,
    in_round,
    in_rounds,
    get_constants,
    get_builtin_constant,
)
from otree.common import has_group_by_arrival_time
from otree.database import db, dbq, values_flat, SPGModel, MixinSessionFK


class GroupMatrixError(ValueError):
    pass


class RoundMismatchError(GroupMatrixError):
    pass


class BaseSubsession(SPGModel, MixinSessionFK):
    __abstract__ = True

    round_number = C(
        st.Integer,
        index=True,
    )

    def in_round(self, round_number):
        return in_round(type(self), round_number, session=self.session)

    def in_rounds(self, first, last):
        return in_rounds(type(self), first, last, session=self.session)

    def in_previous_rounds(self):
        return self.in_rounds(1, self.round_number - 1)

    def in_all_rounds(self):
        return self.in_previous_rounds() + [self]

    def get_groups(self):
        return list(self.group_set.order_by('id_in_subsession'))

    def get_players(self):
        return list(self.player_set.order_by('id'))

    def _get_group_matrix(self, objects):
        Player = self._PlayerClass()
        Group = self._GroupClass()
        players = (
            dbq(Player)
            .join(Group)
            .filter(Player.subsession == self)
            .order_by(Group.id_in_subsession, 'id_in_group')
        )
        d = defaultdict(list)
        for p in players:
            d[p.group.id_in_subsession].append(p if objects else p.id_in_subsession)
        return list(d.values())

    def get_group_matrix(self, objects=False):
        return self._get_group_matrix(objects=objects)

    def set_group_matrix(self, matrix):
        """
        warning: this deletes the groups and any data stored on them
        """

        try:
            sample_item = matrix[0][0]
        except TypeError:
            raise GroupMatrixError('Group matrix must be a list of lists.') from None

        if isinstance(sample_item, SPGModel):
            matrix = [[p.id_in_subsession for p in row] for row in matrix]

        ids_flat = [iis for row in matrix for iis in row]

        ids_flat = sorted(ids_flat)
        players_from_db = self.get_players()

        if not ids_flat == list(range(1, len(players_from_db) + 1)):
            msg = 'The matrix of integers either has duplicate or missing elements.'
            raise GroupMatrixError(msg) from None

        matrix = [[players_from_db[iis - 1] for iis in row] for row in matrix]

        self.player_set.update({self._PlayerClass().group_id: None})
        self.group_set.delete()

        GroupClass = self._GroupClass()
        for i, row in enumerate(matrix, start=1):
            group = GroupClass.objects_create(
                subsession=self,
                id_in_subsession=i,
                session=self.session,
                round_number=self.round_number,
            )
            # this line causes
            # SAWarning: Identity map already had an identity for (<class 'set_group_matrix2.Group'>, (10,), None), replacing it with newly flushed object.   Are there load operations occurring inside of an event handler within the flush?
            #   "within the flush?" % (instance_key,)
            group.set_players(row)

    def group_like_round(self, round_number):
        previous_round: BaseSubsession = self.in_round(round_number)
        group_matrix = previous_round.get_group_matrix()
        self.set_group_matrix(group_matrix)

    @property
    def _Constants(self) -> BaseConstants:
        return get_constants(self.get_folder_name())

    def _GroupClass(self):
        return get_models_module(self.get_folder_name()).Group

    def _PlayerClass(self):
        return get_models_module(self.get_folder_name()).Player

    @classmethod
    def _has_group_by_arrival_time(cls):
        app_name = cls.get_folder_name()
        return has_group_by_arrival_time(app_name)

    def group_randomly(self, *, fixed_id_in_group=False):
        group_matrix = self.get_group_matrix()
        group_matrix = otree.common._group_randomly(group_matrix, fixed_id_in_group)
        self.set_group_matrix(group_matrix)

    def creating_session(self):
        pass

    def vars_for_admin_report(self):
        return {}

    def _gbat_try_to_make_new_group(self, page_index):
        '''Returns the group ID of the participants who were regrouped'''
        from otree.models import Participant

        Player = self._PlayerClass()
        STALE_THRESHOLD_SECONDS = 70

        # count how many are re-grouped
        waiting_players = list(
            self.player_set.join(Participant).filter(
                Participant._gbat_is_connected == True,
                Participant._gbat_tab_hidden == False,
                Participant._index_in_pages == page_index,
                Participant._gbat_grouped == False,
                # this is just a failsafe
                Participant._last_request_timestamp
                >= time.time() - STALE_THRESHOLD_SECONDS,
            )
        )

        target = self.get_user_defined_target()
        # user may not have defined it
        func = getattr(
            target,
            'group_by_arrival_time_method',
            type(self).group_by_arrival_time_method,
        )
        players_for_group = func(self, waiting_players)

        if not players_for_group:
            return None

        participants = [p.participant for p in players_for_group]

        group_id_in_subsession = self._gbat_next_group_id_in_subsession()

        Constants = self._Constants
        num_rounds = Constants.get_normalized('num_rounds')
        this_round_new_group = None
        for round_number in range(self.round_number, num_rounds + 1):
            subsession = self.in_round(round_number)

            unordered_players = subsession.player_set.filter(
                Player.participant_id.in_([pp.id for pp in participants])
            )

            participant_ids_to_players = {
                player.participant: player for player in unordered_players
            }

            ordered_players_for_group = [
                participant_ids_to_players[participant] for participant in participants
            ]

            group = self._GroupClass()(
                subsession=subsession,
                id_in_subsession=group_id_in_subsession,
                session=self.session,
                round_number=round_number,
            )
            db.add(group)
            group.set_players(ordered_players_for_group)

            if round_number == self.round_number:
                this_round_new_group = group

            # prune groups without players
            # https://stackoverflow.com/a/21115972/
            for group_to_delete in subsession.group_set.outerjoin(Player).filter(
                Player.id == None
            ):
                db.delete(group_to_delete)

        for participant in participants:
            participant._gbat_grouped = True
            participant._gbat_is_connected = False

        return this_round_new_group

    def _gbat_next_group_id_in_subsession(self):
        # 2017-05-05: seems like this can result in id_in_subsession that
        # doesn't start from 1.
        # especially if you do group_by_arrival_time in every round
        # is that a problem?
        Group = self._GroupClass()
        return (
            dbq(func.max(Group.id_in_subsession))
            .filter_by(session=self.session)
            .scalar()
            + 1
        )

    def group_by_arrival_time_method(self, waiting_players):
        Constants = self._Constants
        ppg = Constants.get_normalized('players_per_group')

        if ppg is None:
            msg = (
                'If using group_by_arrival_time, you must either set '
                'Constants.players_per_group to a value other than None, '
                'or define group_by_arrival_time_method.'
            )
            raise AssertionError(msg)

        if len(waiting_players) >= ppg:
            return waiting_players[:ppg]

    @declared_attr
    def group_set(cls):
        return relationship(
            f'{cls.__module__}.Group', back_populates="subsession", lazy='dynamic'
        )

    @declared_attr
    def player_set(cls):
        return relationship(
            f'{cls.__module__}.Player', back_populates="subsession", lazy='dynamic'
        )
