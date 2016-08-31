from __future__ import absolute_import

import collections
from six.moves import range
from django.utils.encoding import force_text
from ordered_set import OrderedSet as oset
import easymoney

import otree.constants_internal
from otree.models import Participant, Session
from otree.models_concrete import (
    PageCompletion)


def get_all_fields(Model, for_export=False):
    if Model is PageCompletion:
        return [
            'session_id',
            'participant__id_in_session',
            'participant__code',
            'page_index',
            'app_name',
            'page_name',
            'time_stamp',
            'seconds_on_page',
            'subsession_pk',
            'auto_submitted',
        ]

    if Model is Session:
        return [
            'code',
            'label',
            'experimenter_name',
            'real_world_currency_per_point',
            'time_scheduled',
            'time_started',
            'mturk_HITId',
            'mturk_HITGroupId',
            'participation_fee',
            'comment',
            'is_demo',
            'use_cli_bots',
        ]

    if Model is Participant:
        if for_export:
            return [
                'id_in_session',
                'code',
                'label',
                '_current_page',
                '_current_app_name',
                '_round_number',
                '_current_page_name',
                'ip_address',
                'time_started',
                'exclude_from_data_analysis',
                'visited',
                'mturk_worker_id',
                'mturk_assignment_id',
            ]
        else:
            return [
                '_id_in_session',
                'code',
                'label',
                '_current_page',
                '_current_app_name',
                '_round_number',
                '_current_page_name',
                'status',
                '_last_page_timestamp',
            ]

    first_fields = {
        'Player':
            [
                'id_in_group',
                'role',
            ],
        'Group':
            [
                'id',
            ],
        'Subsession':
            [],
    }[Model.__name__]
    first_fields = oset(first_fields)

    last_fields = {
        'Player': [],
        'Group': [],
        'Subsession': [],
    }[Model.__name__]
    last_fields = oset(last_fields)

    fields_for_export_but_not_view = {
        'Player': {'id', 'label', 'subsession', 'session'},
        'Group': {'id'},
        'Subsession': {'id', 'round_number'},
    }[Model.__name__]

    fields_for_view_but_not_export = {
        'Player': set(),
        'Group': {'subsession', 'session'},
        'Subsession': {'session'},
    }[Model.__name__]

    fields_to_exclude_from_export_and_view = {
        'Player': {
            '_index_in_game_pages',
            'participant',
            'group',
            'subsession',
            'session',
            'round_number',
        },
        'Group': {
            'subsession',
            'id_in_subsession',
            'session',
            '_is_missing_players',
            'round_number',
        },
        'Subsession': {
            'code',
            'label',
            'session',
            'session_access_code',
        },
    }[Model.__name__]

    if for_export:
        fields_to_exclude = fields_to_exclude_from_export_and_view.union(
            fields_for_view_but_not_export
        )
    else:
        fields_to_exclude = fields_to_exclude_from_export_and_view.union(
            fields_for_export_but_not_view
        )

    all_fields_in_model = oset([field.name for field in Model._meta.fields])

    middle_fields = (
        all_fields_in_model - first_fields - last_fields - fields_to_exclude
    )

    return list(first_fields | middle_fields | last_fields)



def get_display_table_rows(app_name, for_export, subsession_pk=None):
    if not for_export and not subsession_pk:
        raise ValueError("if this is for the admin results table, "
                         "you need to specify a subsession pk")
    models_module = otree.common_internal.get_models_module(app_name)
    Player = models_module.Player
    Group = models_module.Group
    Subsession = models_module.Subsession
    if for_export:
        model_order = [
            Participant,
            Player,
            Group,
            Subsession,
            Session
        ]
    else:
        model_order = [
            Player,
            Group,
            Subsession,
        ]

    # get title row
    all_columns = []
    for Model in model_order:
        field_names = get_all_fields(Model, for_export)
        columns_for_this_model = [
            (Model, field_name) for field_name in field_names
            ]
        all_columns.extend(columns_for_this_model)

    if subsession_pk:
        # we had a strange result on one person's heroku instance
        # where Meta.ordering on the Player was being ingnored
        # when you use a filter. So we add one explicitly.
        players = Player.objects.filter(
            subsession_id=subsession_pk).select_related(
            'group', 'subsession').order_by('pk')
    else:
        players = Player.objects.all().select_related(
            'participant', 'group', 'subsession', 'session')

    all_rows = []
    for player in players:
        row = []
        for column in all_columns:
            Model, field_name = column
            if Model == Player:
                model_instance = player
            else:
                model_instance = getattr(player, Model.__name__.lower())
            attr = getattr(model_instance, field_name, '')
            if isinstance(attr, collections.Callable):
                if Model == Player and field_name == 'role' \
                        and model_instance.group is None:
                    attr = ''
                else:
                    try:
                        attr = attr()
                    except:
                        attr = "(error)"
            row.append(attr)
        all_rows.append(row)

    values_to_replace = {None: '', True: 1, False: 0}

    for row in all_rows:
        for i in range(len(row)):
            value = row[i]
            try:
                replace = value in values_to_replace
            except TypeError:
                # if it's an unhashable data type
                # like Json or Pickle field
                replace = False
            if replace:
                value = values_to_replace[value]
            elif for_export and isinstance(value, easymoney.Money):
                # remove currency formatting for easier analysis
                value = easymoney.to_dec(value)
            value = force_text(value)
            value = value.replace('\n', ' ').replace('\r', ' ')
            row[i] = value

    column_display_names = []
    for Model, field_name in all_columns:
        column_display_names.append(
            (Model.__name__, field_name)
        )

    return column_display_names, all_rows
