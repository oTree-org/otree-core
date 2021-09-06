import collections
import csv
import logging
import numbers
from collections import OrderedDict
from collections import defaultdict
from html import escape
from typing import List

from sqlalchemy.sql.functions import func

import otree
from otree.common import get_models_module
from otree.common2 import TimeSpentRow, write_page_completion_buffer
from otree.currency import Currency, RealWorldCurrency
from otree.database import dbq, values_flat
from otree import database
from otree.models.group import BaseGroup
from otree.models.participant import Participant
from otree.models.player import BasePlayer
from otree.models.session import Session
from otree.models.subsession import BaseSubsession
from otree.models_concrete import PageTimeBatch
from otree.session import SessionConfig
from otree import settings

logger = logging.getLogger(__name__)


def inspect_field_names(Model):
    return [f.name for f in Model.__table__.columns]


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
                'time_started_utc',
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
            f for f in inspect_field_names(Model) if f not in dir(BasePlayer)
        ]

        fields = ['id_in_group', 'role', 'payoff'] + subclass_fields
        if for_export:
            return fields
        return ['group'] + fields

    if issubclass(Model, BaseGroup):
        subclass_fields = [
            f for f in inspect_field_names(Model) if f not in dir(BaseGroup)
        ]

        return ['id_in_subsession'] + subclass_fields

    if issubclass(Model, BaseSubsession):
        subclass_fields = [
            f for f in inspect_field_names(Model) if f not in dir(BaseGroup)
        ]

        if for_export:
            return ['round_number'] + subclass_fields
        return subclass_fields


def sanitize_for_csv(value):
    if value is None:
        return ''
    if value is True:
        return 1
    if value is False:
        return 0
    if isinstance(value, (Currency, RealWorldCurrency)):
        # not decimal since that can't be json serialized
        return float(value)
    if isinstance(value, numbers.Number):
        return value
    value = str(value)
    return value.replace('\n', ' ').replace('\r', ' ')


def tweak_player_values_dict(player: dict, group_id_in_subsession=None):
    '''because these are actually properties, the DB field starts with _.'''
    player['payoff'] = player['_payoff']
    player['role'] = player['_role']
    if group_id_in_subsession:
        player['group'] = group_id_in_subsession


def sanitize_for_live_update(value):
    value = escape(str(sanitize_for_csv(value)))
    MAX_LENGTH = 30
    if len(value) > MAX_LENGTH:
        return value[:MAX_LENGTH] + '…'
    return value


def get_installed_apps_with_data() -> list:
    """
    this is just important for devserver.
    on prodserver there should never be an inconsistency between
    currently installed apps and apps with data, because you resetdb each time
    """
    app_names_with_data = set()
    for session in dbq(Session):
        for app_name in session.config['app_sequence']:
            if app_name in settings.OTREE_APPS:
                app_names_with_data.add(app_name)
    return list(sorted(app_names_with_data))


def _get_best_app_order(sessions):
    # heuristic to get the most relevant order of apps
    app_sequences = collections.Counter()
    for session in sessions:
        # we loaded the config earlier
        app_sequence = session.config['app_sequence']
        app_sequences[tuple(app_sequence)] += session.num_participants
    most_common_app_sequence = app_sequences.most_common(1)[0][0]

    app_names_with_data = get_installed_apps_with_data()

    apps_not_in_popular_sequence = [
        app for app in app_names_with_data if app not in most_common_app_sequence
    ]

    return list(most_common_app_sequence) + apps_not_in_popular_sequence


def get_rows_for_wide_csv(session_code):
    if session_code:
        sessions = [Session.objects_get(code=session_code)]
    else:
        sessions = dbq(Session).order_by('id').all()
    session_fields = get_fields_for_csv(Session)
    participant_fields = get_fields_for_csv(Participant)

    session_ids = [session.id for session in sessions]
    pps = (
        Participant.objects_filter(Participant.session_id.in_(session_ids))
        .order_by(Participant.id)
        .all()
    )
    session_cache = {row.id: row for row in sessions}

    session_config_fields = {'name'}
    for session in sessions:
        for field_name in SessionConfig(session.config).editable_fields():
            session_config_fields.add(field_name)
    session_config_fields = list(session_config_fields)

    if not pps:
        # 1 empty row
        return [[]]

    header_row = [f'participant.{fname}' for fname in participant_fields]
    header_row += [f'participant.{fname}' for fname in settings.PARTICIPANT_FIELDS]
    header_row += [f'session.{fname}' for fname in session_fields]
    header_row += [f'session.config.{fname}' for fname in session_config_fields]
    header_row += [f'session.{fname}' for fname in settings.SESSION_FIELDS]
    rows = [header_row]

    for pp in pps:
        session = session_cache[pp.session_id]
        row = [getattr(pp, fname) for fname in participant_fields]
        row += [pp.vars.get(fname, None) for fname in settings.PARTICIPANT_FIELDS]
        row += [getattr(session, fname) for fname in session_fields]
        row += [session.config.get(fname) for fname in session_config_fields]
        row += [session.vars.get(fname, None) for fname in settings.SESSION_FIELDS]
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

        highest_round_number = dbq(
            func.max(models_module.Subsession.round_number)
        ).scalar()

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
    Player: BasePlayer = models_module.Player
    Group: BaseGroup = models_module.Group
    Subsession: BaseSubsession = models_module.Subsession
    pfields = get_fields_for_csv(Player)
    gfields = get_fields_for_csv(Group)
    sfields = get_fields_for_csv(Subsession)

    rows = []
    group_cache = {
        row['id']: row for row in Group.values_dicts(round_number=round_number)
    }

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
        subsessions = Subsession.values_dicts(
            session_id=session.id, round_number=round_number
        )
        if not subsessions:
            subsession_rows = [empty_row for _ in range(session.num_participants)]
        else:
            [subsession] = subsessions
            players = Player.values_dicts(subsession_id=subsession['id'], order_by='id')

            if len(players) != session.num_participants:
                msg = (
                    f"Session {session.code} has {session.num_participants} participants, "
                    f"but round {round_number} of app '{app_name}' "
                    f"has {len(players)} players. The number of players in the subsession "
                    "should always match the number of players in the session. "
                    "Please report this issue and then reset the database."
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

    session_ids = values_flat(dbq(Subsession), Subsession.session_id)

    players = Player.values_dicts(order_by='id')

    value_dicts = dict(
        group={row['id']: row for row in Group.values_dicts()},
        subsession={row['id']: row for row in Subsession.values_dicts()},
        # before we used Participant.id.in_(...)
        # but a user got an error that the "in" clause of the query had too many vars
        participant={
            row['id']: row
            for row in Participant.values_dicts(Participant.session_id.in_(session_ids))
        },
        session={
            row['id']: row for row in Session.values_dicts(Session.id.in_(session_ids))
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

    players = Player.values_dicts(session=session, order_by='id')

    players_by_round = defaultdict(list)
    for p in players:
        players_by_round[p['round_number']].append(p)

    groups = {g['id']: g for g in Group.values_dicts(session=session)}
    subsessions = {s['id']: s for s in Subsession.values_dicts(session=session)}

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
            table.append([sanitize_for_live_update(v) for v in row])
        yield table


def export_wide(fp, session_code=None):
    rows = get_rows_for_wide_csv(session_code=session_code)
    _export_csv(fp, rows)


def export_app(app_name, fp):
    rows = get_rows_for_csv(app_name)
    _export_csv(fp, rows)


from sqlalchemy.orm import joinedload


def custom_export_app(app_name, fp):
    models_module = get_models_module(app_name)
    Player = models_module.Player
    qs = list(
        dbq(Player)
        .order_by('id')
        .options(
            joinedload(Player.participant, innerjoin=True),
            joinedload(Player.group, innerjoin=True),
            joinedload(Player.subsession, innerjoin=True),
            joinedload(Player.session, innerjoin=True),
        )
    )
    for player in qs:
        # need this to query null values
        player._is_frozen = False
    rows = models_module.custom_export(qs)
    str_rows = []
    for row in rows:
        str_rows.append([sanitize_for_csv(ele) for ele in row])
    _export_csv(fp, str_rows)


def _export_csv(fp, rows):
    writer = csv.writer(fp)
    writer.writerows(rows)


def export_page_times(fp):
    write_page_completion_buffer()
    batches = values_flat(dbq(PageTimeBatch).order_by('id'), PageTimeBatch.text)
    fp.write(','.join(TimeSpentRow.__annotations__.keys()) + '\n')
    for batch in batches:
        fp.write(batch)


BOM = '\ufeff'
