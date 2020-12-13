from otree.db import models
from otree.common import (
    get_models_module,
    in_round,
    in_rounds,
    InvalidRoundError,
)
from otree import common
import django.core.exceptions
from django.db import models as djmodels
from otree.constants import BaseConstants, get_role, get_roles
from otree.db.idmap import GroupIDMapMixin


class BaseGroup(models.OTreeModel, GroupIDMapMixin):
    class Meta:
        abstract = True
        index_together = ['session', 'id_in_subsession']
        ordering = ['pk']

    id_in_subsession = models.PositiveIntegerField(db_index=True)

    session = djmodels.ForeignKey(
        'otree.Session',
        related_name='%(app_label)s_%(class)s',
        on_delete=models.CASCADE,
    )

    round_number = models.PositiveIntegerField(db_index=True)

    @property
    def _Constants(self) -> BaseConstants:
        return get_models_module(self._meta.app_config.name).Constants

    def __unicode__(self):
        return str(self.pk)

    def get_players(self):
        return list(self.player_set.order_by('id_in_group'))

    def get_player_by_id(self, id_in_group):
        try:
            return self.player_set.get(id_in_group=id_in_group)
        except django.core.exceptions.ObjectDoesNotExist:
            msg = 'No player with id_in_group {}'.format(id_in_group)
            raise ValueError(msg) from None

    def get_player_by_role(self, role):
        if get_roles(self._Constants):
            try:
                return self.player_set.get(_role=role)
            except django.core.exceptions.ObjectDoesNotExist:
                pass
        else:
            for p in self.get_players():
                if p.role() == role:
                    return p
        msg = f'No player with role "{role}"'
        raise ValueError(msg)

    def set_players(self, players_list):
        Constants = self._Constants
        roles = get_roles(Constants)
        for i, player in enumerate(players_list, start=1):
            player.group = self
            player.id_in_group = i
            player._role = get_role(roles, i)
            player.save()

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

    @classmethod
    def _ensure_required_fields(cls):
        """
        Every ``Group`` model requires a foreign key to the ``Subsession``
        model of the same app.
        """
        subsession_model = '{app_label}.Subsession'.format(
            app_label=cls._meta.app_label
        )
        subsession_field = djmodels.ForeignKey(
            subsession_model, on_delete=models.CASCADE
        )
        subsession_field.contribute_to_class(cls, 'subsession')
