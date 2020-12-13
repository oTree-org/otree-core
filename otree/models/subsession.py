import time
from django.db.models import Prefetch
from django.db.models import Max

import otree.common
from otree.db import models
from otree.common import get_models_module, in_round, in_rounds, ResponseForException
import copy
from otree.common import has_group_by_arrival_time
from django.apps import apps
from django.db import models as djmodels
from otree.db.idmap import SubsessionIDMapMixin


class GroupMatrixError(ValueError):
    pass


class RoundMismatchError(GroupMatrixError):
    pass


class BaseSubsession(models.OTreeModel, SubsessionIDMapMixin):
    """Base class for all Subsessions.
    """

    class Meta:
        abstract = True
        ordering = ['pk']
        index_together = ['session', 'round_number']

    session = djmodels.ForeignKey(
        'otree.Session',
        related_name='%(app_label)s_%(class)s',
        null=True,
        on_delete=models.CASCADE,
    )

    round_number = models.PositiveIntegerField(
        db_index=True,
        doc='''If this subsession is repeated (i.e. has multiple rounds), this
        field stores the position of this subsession, among subsessions
        in the same app.
        ''',
    )

    def in_round(self, round_number):
        return in_round(type(self), round_number, session=self.session)

    def in_rounds(self, first, last):
        return in_rounds(type(self), first, last, session=self.session)

    def in_previous_rounds(self):
        return self.in_rounds(1, self.round_number - 1)

    def in_all_rounds(self):
        return self.in_previous_rounds() + [self]

    def __unicode__(self):
        return str(self.pk)

    def get_groups(self):
        return list(self.group_set.order_by('id_in_subsession'))

    def get_players(self):
        return list(self.player_set.order_by('pk'))

    def get_group_matrix(self):
        players_prefetch = Prefetch(
            'player_set',
            queryset=self._PlayerClass().objects.order_by('id_in_group'),
            to_attr='_ordered_players',
        )
        return [
            group._ordered_players
            for group in self.group_set.order_by('id_in_subsession').prefetch_related(
                players_prefetch
            )
        ]

    def set_group_matrix(self, matrix):
        """
        warning: this deletes the groups and any data stored on them
        TODO: we should indicate this in docs
        """

        try:
            players_flat = [p for g in matrix for p in g]
        except TypeError:
            raise GroupMatrixError('Group matrix must be a list of lists.') from None
        try:
            matrix_pks = sorted(p.pk for p in players_flat)
        except AttributeError:
            # if integers, it's OK
            if isinstance(players_flat[0], int):
                # deep copy so that we don't modify the input arg
                matrix = copy.deepcopy(matrix)
                players_flat = sorted(players_flat)
                players_from_db = self.get_players()
                if players_flat == list(range(1, len(players_from_db) + 1)):
                    for i, row in enumerate(matrix):
                        for j, val in enumerate(row):
                            matrix[i][j] = players_from_db[val - 1]
                else:
                    msg = (
                        'If you pass a matrix of integers to this function, '
                        'It must contain all integers from 1 to '
                        'the number of players in the subsession.'
                    )
                    raise GroupMatrixError(msg) from None
            else:
                msg = (
                    'The elements of the group matrix '
                    'must either be Player objects, or integers.'
                )
                raise GroupMatrixError(msg) from None
        else:
            existing_pks = list(
                self.player_set.values_list('pk', flat=True).order_by('pk')
            )
            if matrix_pks != existing_pks:
                wrong_round_numbers = [
                    p.round_number
                    for p in players_flat
                    if p.round_number != self.round_number
                ]
                if wrong_round_numbers:
                    msg = (
                        'You are setting the groups for round {}, '
                        'but the matrix contains players from round {}.'.format(
                            self.round_number, wrong_round_numbers[0]
                        )
                    )
                    raise GroupMatrixError(msg)
                msg = (
                    'The group matrix must contain each player '
                    'in the subsession exactly once.'
                )
                raise GroupMatrixError(msg)

        # Before deleting groups, Need to set the foreignkeys to None
        # 2016-11-8: does this need to be in a transaction?
        # because what if a player refreshes their page while this is going
        # on?
        self.player_set.update(group=None)
        self.group_set.all().delete()

        GroupClass = self._GroupClass()
        for i, row in enumerate(matrix, start=1):
            group = GroupClass.objects.create(
                subsession=self,
                id_in_subsession=i,
                session=self.session,
                round_number=self.round_number,
            )
            group.set_players(row)

    def group_like_round(self, round_number):
        previous_round = self.in_round(round_number)
        group_matrix = [
            group._ordered_players
            for group in previous_round.group_set.order_by(
                'id_in_subsession'
            ).prefetch_related(
                Prefetch(
                    'player_set',
                    queryset=self._PlayerClass().objects.order_by('id_in_group'),
                    to_attr='_ordered_players',
                )
            )
        ]
        for i, group_list in enumerate(group_matrix):
            for j, player in enumerate(group_list):
                # for every entry (i,j) in the matrix, follow the pointer
                # to the same person in the next round
                group_matrix[i][j] = player.in_round(self.round_number)

        self.set_group_matrix(group_matrix)

    @property
    def _Constants(self):
        return get_models_module(self._meta.app_config.name).Constants

    def _GroupClass(self):
        return apps.get_model(self._meta.app_config.label, 'Group')

    def _PlayerClass(self):
        return apps.get_model(self._meta.app_config.label, 'Player')

    @classmethod
    def _has_group_by_arrival_time(cls):
        return has_group_by_arrival_time(cls._meta.app_config.name)

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

        STALE_THRESHOLD_SECONDS = 20

        # count how many are re-grouped
        waiting_players = list(
            self.player_set.filter(
                participant___gbat_is_waiting=True,
                participant___index_in_pages=page_index,
                participant___gbat_grouped=False,
                participant___last_request_timestamp__gte=time.time()
                - STALE_THRESHOLD_SECONDS,
            )
        )

        try:
            players_for_group = self.group_by_arrival_time_method(waiting_players)
        except:
            raise ResponseForException

        if not players_for_group:
            return None

        participants = [p.participant for p in players_for_group]

        group_id_in_subsession = self._gbat_next_group_id_in_subsession()

        Constants = self._Constants

        this_round_new_group = None
        with otree.common.transaction_except_for_sqlite():
            for round_number in range(self.round_number, Constants.num_rounds + 1):
                subsession = self.in_round(round_number)

                unordered_players = subsession.player_set.filter(
                    participant__in=participants
                )

                participant_ids_to_players = {
                    player.participant: player for player in unordered_players
                }

                ordered_players_for_group = [
                    participant_ids_to_players[participant]
                    for participant in participants
                ]

                group = self._GroupClass().objects.create(
                    subsession=subsession,
                    id_in_subsession=group_id_in_subsession,
                    session=self.session,
                    round_number=round_number,
                )
                group.set_players(ordered_players_for_group)

                if round_number == self.round_number:
                    this_round_new_group = group

                # prune groups without players
                # apparently player__isnull=True works, didn't know you could
                # use this in a reverse direction.
                subsession.group_set.filter(player__isnull=True).delete()

        for participant in participants:
            participant._gbat_grouped = True
            participant._gbat_is_waiting = False

        return this_round_new_group

    def _gbat_next_group_id_in_subsession(self):
        # 2017-05-05: seems like this can result in id_in_subsession that
        # doesn't start from 1.
        # especially if you do group_by_arrival_time in every round
        # is that a problem?
        res = (
            self._GroupClass()
            .objects.filter(session=self.session)
            .aggregate(Max('id_in_subsession'))
        )
        return res['id_in_subsession__max'] + 1

    def group_by_arrival_time_method(self, waiting_players):
        Constants = self._Constants

        if Constants.players_per_group is None:
            msg = (
                'Page "{}": if using group_by_arrival_time, you must either set '
                'Constants.players_per_group to a value other than None, '
                'or define group_by_arrival_time_method.'.format(
                    self.__class__.__name__
                )
            )
            raise AssertionError(msg)

        if len(waiting_players) >= Constants.players_per_group:
            return waiting_players[: Constants.players_per_group]
