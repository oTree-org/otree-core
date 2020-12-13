import collections
from typing import List
import csv
import logging
import numbers
from collections import OrderedDict
from collections import defaultdict
from decimal import Decimal

from django.db.models import BinaryField, ForeignKey
from django.db.models import Max
from django.utils.encoding import force_text
from django.utils.html import escape

import otree
from otree.common import get_models_module
from otree.common2 import TIME_SPENT_COLUMNS, write_page_completion_buffer
from otree.currency import Currency, RealWorldCurrency
from otree.models.group import BaseGroup
from otree.models.participant import Participant
from otree.models.player import BasePlayer
from otree.models.session import Session
from otree.models.subsession import BaseSubsession
from otree.models_concrete import PageTimeBatch
from otree.session import SessionConfig

logger = logging.getLogger(__name__)


def inspect_field_names(Model):
    # filter out BinaryField, because it's not useful for CSV export or
    # live results. could be very big, and causes problems with utf-8 export

    # I tried .get_fields() instead of .fields, but that method returns
    # fields that cause problems, like saying group has an attribute 'player'
    field_names = []
    for f in Model._meta.fields:
        if not isinstance(f, BinaryField):
            if isinstance(f, ForeignKey):
                field_names.append('{}_id'.format(f.name))
            else:
                field_names.append(f.name)

    return field_names


def get_fields_for_data_tab(app_name):
    models_module = get_models_module(app_name)
    for Model in [models_module.Player, models_module.Group, models_module.Subsession]:
        yield _get_table_fields(Model, for_export=False)


def get_fields_for_monitor():
    return _get_table_fields(Participant, for_export=False)


def get_fields_for_csv(Model):
    return _get_table_fields(Model, for_export=True)


def _get_table_fields(Model, for_export=False):

    if Model is Session:
        # only data export
        return [
            'code',
            'label',
            'mturk_HITId',
            'mturk_HITGroupId',
            'comment',
            'is_demo',
        ]

    if Model is Participant:
        if for_export:
            return [
                'id_in_session',
                'code',
                'label',
                '_is_bot',
                '_index_in_pages',
                '_max_page_index',
                '_current_app_name',
                # this could be confusing because it will be in every row,
                # even rows for different rounds.
                #'_round_number',
                '_current_page_name',
                'time_started',
                'visited',
                'mturk_worker_id',
                'mturk_assignment_id',
                # last so that it will be next to payoff_plus_participation_fee
                'payoff',
            ]
        else:
            return [
                '_numeric_label',
                'code',
                'label',
                '_current_page',
                '_current_app_name',
                '_round_number',
                '_current_page_name',
                '_monitor_note',
                '_last_page_timestamp',
            ]

    if issubclass(Model, BasePlayer):
        subclass_fields = [
            f
            for f in inspect_field_names(Model)
            if f not in inspect_field_names(BasePlayer)
            and f not in ['id', 'group_id', 'subsession_id']
        ]

        fields = ['id_in_group', 'role', 'payoff'] + subclass_fields
        if for_export:
            return fields
        return ['group'] + fields

    if issubclass(Model, BaseGroup):
        subclass_fields = [
            f
            for f in inspect_field_names(Model)
            if f not in inspect_field_names(BaseGroup)
            and f not in ['id', 'subsession_id']
        ]

        return ['id_in_subsession'] + subclass_fields

    if issubclass(Model, BaseSubsession):
        subclass_fields = [
            f
            for f in inspect_field_names(Model)
            if f not in inspect_field_names(BaseGroup) and f != 'id'
        ]

        if for_export:
            return ['round_number'] + subclass_fields
        return subclass_fields


def sanitize_for_csv(value) -> str:
    if value is None:
        return ''
    if value is True:
        return 1
    if value is False:
        return 0
    if isinstance(value, (Currency, RealWorldCurrency)):
        # FIXME: django 1.11 upgrade: make sure querying currency values
        # doesn't slow it down too much (behavior of .values() changed)
        # Alexander has an idea, contact him if it's slow
        return Decimal(value)
    if isinstance(value, numbers.Number):
        return value
    value = force_text(value)
    return value.replace('\n', ' ').replace('\r', ' ')


def tweak_player_values_dict(player: dict, group_id_in_subsession=None):
    '''because these are actually properties, the DB field starts with _.'''
    player['payoff'] = player['_payoff']
    player['role'] = player['_role']
    if group_id_in_subsession:
        player['group'] = group_id_in_subsession


def sanitize_for_live_update(value):
    value = escape(sanitize_for_csv(value))
    MAX_LENGTH = 30
    if len(value) > MAX_LENGTH:
        return value[:MAX_LENGTH] + '…'
    return value


def get_payoff_plus_participation_fee(session, participant_values_dict):
    payoff = Currency(participant_values_dict['payoff'])
    return session._get_payoff_plus_participation_fee(payoff)


def _get_best_app_order(sessions):
    # heuristic to get the most relevant order of apps
    app_sequences = collections.Counter()
    for session in sessions:
        # we loaded the config earlier
        app_sequence = session.config['app_sequence']
        app_sequences[tuple(app_sequence)] += session.num_participants
    most_common_app_sequence = app_sequences.most_common(1)[0][0]

    # can't use settings.INSTALLED_OTREE_APPS, because maybe the app
    # was removed from SESSION_CONFIGS.
    app_names_with_data = set()
    for session in sessions:
        for app_name in session.config['app_sequence']:
            app_names_with_data.add(app_name)

    apps_not_in_popular_sequence = [
        app for app in app_names_with_data if app not in most_common_app_sequence
    ]

    return list(most_common_app_sequence) + apps_not_in_popular_sequence


def get_rows_for_wide_csv(session_code):
    if session_code:
        sessions = [Session.objects.get(code=session_code)]
    else:
        sessions = Session.objects.order_by('id')
    participants = (
        Participant.objects.filter(session__in=sessions).order_by('id').values()
    )
    session_cache = {row.id: row for row in sessions}

    session_config_fields = set()
    for session in sessions:
        for field_name in SessionConfig(session.config).editable_fields():
            session_config_fields.add(field_name)
    session_config_fields = list(session_config_fields)

    if not participants:
        # 1 empty row
        return [[]]

    session_fields = get_fields_for_csv(Session)
    participant_fields = get_fields_for_csv(Participant)
    header_row = [f'participant.{fname}' for fname in participant_fields]
    header_row += [f'session.{fname}' for fname in session_fields]
    header_row += [f'session.config.{fname}' for fname in session_config_fields]
    rows = [header_row]
    for participant in participants:
        session = session_cache[participant['session_id']]
        row = [participant[fname] for fname in participant_fields]
        row += [getattr(session, fname) for fname in session_fields]
        row += [session.config.get(fname) for fname in session_config_fields]
        rows.append(row)

    order_of_apps = _get_best_app_order(sessions)

    rounds_per_app = OrderedDict()
    for app_name in order_of_apps:
        try:
            models_module = get_models_module(app_name)
        except ModuleNotFoundError:
            # this should only happen with devserver because on production server,
            # you would need to resetdb after renaming an app.
            logger.warning(
                f'Cannot export data for app {app_name}, which existed when the session was run '
                f'but no longer exists.'
            )
            continue
        agg_dict = models_module.Subsession.objects.all().aggregate(Max('round_number'))
        highest_round_number = agg_dict['round_number__max']

        if highest_round_number is not None:
            rounds_per_app[app_name] = highest_round_number
    for app_name in rounds_per_app:
        for round_number in range(1, rounds_per_app[app_name] + 1):
            new_rows = get_rows_for_wide_csv_round(app_name, round_number, sessions)
            for i in range(len(rows)):
                rows[i].extend(new_rows[i])

    return [[sanitize_for_csv(v) for v in row] for row in rows]


def get_rows_for_wide_csv_round(app_name, round_number, sessions: List[Session]):

    models_module = otree.common.get_models_module(app_name)
    Player = models_module.Player
    Group = models_module.Group
    Subsession = models_module.Subsession

    rows = []
    group_cache = {
        row['id']: row
        for row in Group.objects.filter(round_number=round_number).values()
    }

    pfields = get_fields_for_csv(Player)
    gfields = get_fields_for_csv(Group)
    sfields = get_fields_for_csv(Subsession)

    header_row = []
    for model_name, fields in [
        ('player', pfields),
        ('group', gfields),
        ('subsession', sfields),
    ]:
        for fname in fields:
            header_row.append(f'{app_name}.{round_number}.{model_name}.{fname}')
    rows.append(header_row)
    empty_row = ['' for _ in range(len(header_row))]

    for session in sessions:
        subsessions = Subsession.objects.filter(
            session_id=session.id, round_number=round_number
        ).values()
        if not subsessions:
            subsession_rows = [empty_row for _ in range(session.num_participants)]
        else:
            [subsession] = subsessions
            players = (
                Player.objects.filter(subsession_id=subsession['id'])
                .order_by('id')
                .values()
            )

            if len(players) != session.num_participants:
                msg = (
                    f"Session {session.code} has {session.num_participants} participants, "
                    f"but round {round_number} of app '{app_name}' "
                    f"has {len(players)} players. The number of players in the subsession "
                    "should always match the number of players in the session. "
                    "Reset the database and examine your code."
                )
                raise AssertionError(msg)

            subsession_rows = []

            for player in players:
                group = group_cache[player['group_id']]
                tweak_player_values_dict(player)

                row = [player[fname] for fname in pfields]
                row += [group[fname] for fname in gfields]
                row += [subsession[fname] for fname in sfields]

                subsession_rows.append(row)
        rows.extend(subsession_rows)
    return rows


def get_rows_for_csv(app_name):
    # need to use app_name and not app_label because the app might have been
    # removed from SESSION_CONFIGS
    models_module = otree.common.get_models_module(app_name)
    Player = models_module.Player
    Group = models_module.Group
    Subsession = models_module.Subsession

    columns_for_models = {
        Model.__name__.lower(): get_fields_for_csv(Model)
        for Model in [Player, Group, Subsession, Participant, Session]
    }

    participant_ids = Player.objects.values_list('participant_id', flat=True)
    session_ids = Subsession.objects.values_list('session_id', flat=True)

    players = Player.objects.order_by('id').values()

    value_dicts = dict(
        group={row['id']: row for row in Group.objects.values()},
        subsession={row['id']: row for row in Subsession.objects.values()},
        participant={
            row['id']: row
            for row in Participant.objects.filter(id__in=participant_ids).values()
        },
        session={
            row['id']: row
            for row in Session.objects.filter(id__in=session_ids).values()
        },
    )

    model_order = ['participant', 'player', 'group', 'subsession', 'session']

    # header row
    rows = [[f'{m}.{col}' for m in model_order for col in columns_for_models[m]]]

    for player in players:
        tweak_player_values_dict(player)
        row = []

        for model_name in model_order:
            if model_name == 'player':
                obj = player
            else:
                obj = value_dicts[model_name][player[f'{model_name}_id']]
            for colname in columns_for_models[model_name]:
                row.append(sanitize_for_csv(obj[colname]))
        rows.append(row)

    return rows


def get_rows_for_monitor(participants) -> list:
    field_names = get_fields_for_monitor()
    callable_fields = {'_numeric_label', '_current_page'}
    rows = []
    for participant in participants:
        row = {}
        for field_name in field_names:
            value = getattr(participant, field_name)
            if field_name in callable_fields:
                value = value()
            row[field_name] = value
        row['id_in_session'] = participant.id_in_session
        rows.append(row)
    return rows


def get_rows_for_data_tab(session):
    for app_name in session.config['app_sequence']:
        yield from get_rows_for_data_tab_app(session, app_name)


def get_rows_for_data_tab_app(session, app_name):
    models_module = get_models_module(app_name)
    Player = models_module.Player
    Group = models_module.Group
    Subsession = models_module.Subsession

    pfields, gfields, sfields = get_fields_for_data_tab(app_name)

    players = Player.objects.filter(session=session).order_by('pk').values()

    players_by_round = defaultdict(list)
    for p in players:
        players_by_round[p['round_number']].append(p)

    groups = {g['id']: g for g in Group.objects.filter(session=session).values()}
    subsessions = {
        s['id']: s for s in Subsession.objects.filter(session=session).values()
    }

    for round_number in range(1, len(subsessions) + 1):
        table = []
        for p in players_by_round[round_number]:
            g = groups[p['group_id']]
            tweak_player_values_dict(p, g['id_in_subsession'])
            s = subsessions[p['subsession_id']]
            row = (
                [p[fname] for fname in pfields]
                + [g[fname] for fname in gfields]
                + [s[fname] for fname in sfields]
            )
            table.append([sanitize_for_csv(v) for v in row])
        yield table


def export_wide(fp, session_code=None):
    rows = get_rows_for_wide_csv(session_code=session_code)
    _export_csv(fp, rows)


def export_app(app_name, fp):
    rows = get_rows_for_csv(app_name)
    _export_csv(fp, rows)


def custom_export_app(app_name, fp):
    models_module = get_models_module(app_name)
    qs = models_module.Player.objects.select_related(
        'participant', 'group', 'subsession', 'session'
    ).order_by('id')
    rows = models_module.custom_export(qs)
    # convert to strings so we don't get errors especially for Excel
    str_rows = []
    for row in rows:
        str_rows.append([str(ele) for ele in row])
    _export_csv(fp, str_rows)


def _export_csv(fp, rows):
    writer = csv.writer(fp)
    writer.writerows(rows)


def export_page_times(fp):
    write_page_completion_buffer()
    batches = PageTimeBatch.objects.order_by('id').values_list('text', flat=True)
    fp.write(','.join(TIME_SPENT_COLUMNS) + '\n')
    for batch in batches:
        fp.write(batch)
