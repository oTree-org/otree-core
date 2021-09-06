from collections import defaultdict
from decimal import Decimal
from functools import reduce
from typing import List, Dict
from otree import settings

from otree.database import db, dbq
from otree import common
from otree.common import (
    get_models_module,
    get_builtin_constant,
    validate_alphanumeric,
    get_bots_module,
    get_constants,
)
from otree.currency import RealWorldCurrency
from otree.models import Participant, Session
from otree.constants import BaseConstants, get_roles, get_role


def gcd(a, b):
    """Return greatest common divisor using Euclid's Algorithm."""
    while b:
        a, b = b, a % b
    return a


def lcm(a, b):
    """Return lowest common multiple."""
    return a * b // gcd(a, b)


def lcmm(*args):
    """Return lcm of args."""
    return reduce(lcm, args)


class SessionConfigError(Exception):
    pass


NON_EDITABLE_FIELDS = {
    'name',
    'display_name',
    'app_sequence',
    'num_demo_participants',
    'doc',
}


class SessionConfig(dict):

    # convenient access
    @property
    def app_sequence(self) -> list:
        return self['app_sequence']

    @property
    def participation_fee(self) -> RealWorldCurrency:
        return self['participation_fee']

    def get_lcm(self):
        min_multiple_list = []
        for app_name in self['app_sequence']:
            # if players_per_group is None, 0, etc.
            min_multiple = get_builtin_constant(app_name, 'players_per_group') or 1
            min_multiple_list.append(min_multiple)
        return lcmm(*min_multiple_list)

    def get_num_bot_cases(self):
        num_cases = 1
        for app_name in self['app_sequence']:
            bots_module = get_bots_module(app_name)
            cases = bots_module.PlayerBot.cases
            num_cases = max(num_cases, len(cases))
        return num_cases

    def clean(self):
        for k in ['participation_fee', 'real_world_currency_per_point']:
            if k not in self:
                msg = f'SESSION_CONFIG_DEFAULTS is missing {k}'
                raise SessionConfigError(msg)
        for k in ['name', 'app_sequence', 'num_demo_participants']:
            if k not in self:
                msg = f'Session config is missing {k}'
                raise SessionConfigError(msg)

        validate_alphanumeric(
            self['name'], identifier_description='settings.SESSION_CONFIGS name'
        )

        app_sequence = self['app_sequence']
        if len(app_sequence) != len(set(app_sequence)):
            msg = (
                'settings.SESSION_CONFIGS: '
                'app_sequence of "{}" '
                'must not contain duplicate elements. '
                'If you want multiple rounds, '
                'you should set num_rounds.'
            )
            raise SessionConfigError(msg.format(self['name']))

        if len(app_sequence) == 0:
            msg = 'settings.SESSION_CONFIGS: app_sequence cannot be empty.'
            raise SessionConfigError(msg)

        self.setdefault('display_name', self['name'])
        self.setdefault('doc', '')

        self['participation_fee'] = RealWorldCurrency(self['participation_fee'])

    def app_sequence_display(self):
        app_sequence = []
        for app_name in self['app_sequence']:
            num_rounds = get_builtin_constant(app_name, 'num_rounds')
            models_module = get_models_module(app_name)
            if num_rounds > 1:
                formatted_app_name = '{} ({} rounds)'.format(app_name, num_rounds)
            else:
                formatted_app_name = app_name
            subsssn = {
                'doc': getattr(models_module, 'doc', ''),
                'name': formatted_app_name,
            }
            app_sequence.append(subsssn)
        return app_sequence

    def builtin_editable_fields(self):
        fields = ['participation_fee']
        if settings.USE_POINTS:
            fields.append('real_world_currency_per_point')
        return fields

    def custom_editable_fields(self):
        # should there also be some restriction on
        # what chars are allowed? because maybe not all chars work
        # in an HTML form field (e.g. periods, quotes, etc)
        # so far, it seems any char works OK, even without escaping
        # before making an HTML attribute. even '>漢 ."&'
        # so i'll just put a general recommendation in the docs

        return [
            k
            for k, v in self.items()
            if k not in NON_EDITABLE_FIELDS
            and k not in self.builtin_editable_fields()
            and type(v) in [bool, int, float, str]
        ]

    def editable_fields(self):
        return self.builtin_editable_fields() + self.custom_editable_fields()

    def html_field_name(self, field_name):
        return '{}.{}'.format(self['name'], field_name)

    def editable_field_html(self, field_name):
        existing_value = self[field_name]
        html_field_name = self.html_field_name(field_name)
        base_attrs = ["name='{}'".format(html_field_name)]

        if isinstance(existing_value, bool):
            attrs = [
                "type='checkbox'",
                'checked' if existing_value else '',
                # don't use class=form-control because it looks too big,
                # like it's intended for mobile devices
            ]
        elif isinstance(existing_value, int):
            attrs = [
                "type='number'",
                "required",
                "step='1'",
                "value='{}'".format(existing_value),
                "class='form-control'",
            ]
        elif isinstance(existing_value, (float, Decimal)):
            # convert to float, e.g. participation_fee
            attrs = [
                "class='form-control'",
                "type='number'",
                "step='any'",
                "required",
                "value='{}'".format(float(existing_value)),
            ]
        elif isinstance(existing_value, str):
            attrs = [
                "type='text'",
                "value='{}'".format(existing_value),
                "class='form-control'",
            ]
        html = '''
        <tr><td><b>{}</b><td><input {}></td>
        '''.format(
            field_name, ' '.join(base_attrs + attrs)
        )
        return html

    def builtin_editable_fields_html(self):
        return [self.editable_field_html(k) for k in self.builtin_editable_fields()]

    def custom_editable_fields_html(self):
        return [self.editable_field_html(k) for k in self.custom_editable_fields()]


def get_session_configs_dict(
    SESSION_CONFIGS: List[Dict], SESSION_CONFIG_DEFAULTS: Dict
):
    SESSION_CONFIGS_DICT = {}
    for config_dict in SESSION_CONFIGS:
        config_obj = SessionConfig(SESSION_CONFIG_DEFAULTS)
        config_obj.update(config_dict)
        config_obj.clean()
        config_name = config_dict['name']
        if config_name in SESSION_CONFIGS_DICT:
            msg = f"Duplicate SESSION_CONFIG name: {config_name}"
            raise SessionConfigError(msg)
        SESSION_CONFIGS_DICT[config_name] = config_obj
    return SESSION_CONFIGS_DICT


SESSION_CONFIGS_DICT = get_session_configs_dict(
    settings.SESSION_CONFIGS, settings.SESSION_CONFIG_DEFAULTS
)


class CreateSessionInvalidArgs(ValueError):
    pass


def create_session(
    session_config_name,
    *,
    num_participants,
    label='',
    room_name=None,
    is_mturk=False,
    is_demo=False,
    modified_session_config_fields=None,
) -> Session:

    num_subsessions = 0

    try:
        session_config = SESSION_CONFIGS_DICT[session_config_name]
    except KeyError:
        msg = 'Session config "{}" not found in settings.SESSION_CONFIGS.'
        raise CreateSessionInvalidArgs(msg.format(session_config_name)) from None
    else:
        # copy so that we don't mutate the original
        # .copy() returns a dict, so need to convert back to SessionConfig
        session_config = SessionConfig(session_config.copy())

        modified_config = modified_session_config_fields or {}
        # this is for API. don't want to mislead people
        # to put stuff in the session config that should be in the session.
        bad_keys = modified_config.keys() & NON_EDITABLE_FIELDS
        if bad_keys:
            raise CreateSessionInvalidArgs(
                f'The following session config fields are not editable: {bad_keys}'
            )
        session_config.update(modified_config)

        # check validity and converts serialized decimal & currency values
        # back to their original data type (because they were serialized
        # when passed through channels
        session_config.clean()

    # check that it divides evenly
    session_lcm = session_config.get_lcm()
    if num_participants is None:
        # most games are multiplayer, so if it's under 2, we bump it to 2
        num_participants = max(session_lcm, 2)
    else:
        if num_participants % session_lcm:
            msg = (
                'Session Config {}: Number of participants ({}) is not a multiple '
                'of group size ({})'
            ).format(session_config['name'], num_participants, session_lcm)
            raise CreateSessionInvalidArgs(msg)

    session = Session(
        config=session_config,
        label=label,
        is_demo=is_demo,
        num_participants=num_participants,
        is_mturk=is_mturk,
    )
    db.add(session)

    # i think the .commit() is necessary for the object to have a PK, so that FKs can work,
    # etc.
    db.commit()

    try:
        session_code = session.code
        participants = [
            Participant(
                id_in_session=id_in_session,
                session=session,
                _session_code=session_code,
            )
            for id_in_session in list(range(1, num_participants + 1))
        ]

        db.add_all(participants)
        db.commit()

        # participant_values = (
        #     db.query(Participant)
        #     .filter(Session.id == session.id)
        #     .order_by('id')
        #     .with_entities(Participant.id, Participant.code)
        # ).all()

        participant_values = (
            db.query(Participant)
            .join(Session)
            .filter(Session.id == session.id)
            .order_by(Participant.id)
            .with_entities(Participant.id, Participant.code)
        ).all()

        num_pages = 0

        for app_name in session_config['app_sequence']:

            views_module = common.get_pages_module(app_name)
            models_module = get_models_module(app_name)
            num_rounds = get_builtin_constant(app_name, 'num_rounds')
            num_subsessions += num_rounds

            round_numbers = list(range(1, num_rounds + 1))

            num_pages += num_rounds * len(views_module.page_sequence)

            Subsession = models_module.Subsession
            Group = models_module.Group
            Player = models_module.Player
            Constants = get_constants(app_name)

            subsessions = [
                Subsession(round_number=round_number, session=session)
                for round_number in round_numbers
            ]

            db.add_all(subsessions)
            db.commit()

            subsessions = (
                dbq(Subsession)
                .filter_by(session=session)
                .order_by('round_number')
                .with_entities('id', 'round_number')
            )

            ppg = Constants.get_normalized('players_per_group')
            if ppg is None or Subsession._has_group_by_arrival_time():
                ppg = num_participants

            num_groups_per_round = int(num_participants / ppg)

            groups_to_create = []
            for ss_id, ss_rd in subsessions:
                for id_in_subsession in range(1, num_groups_per_round + 1):
                    groups_to_create.append(
                        Group(
                            session=session,
                            subsession_id=ss_id,
                            round_number=ss_rd,
                            id_in_subsession=id_in_subsession,
                        )
                    )

            db.add_all(groups_to_create)

            groups = (
                dbq(Group).filter_by(session=session).order_by('id_in_subsession')
            ).all()

            groups_lookup = defaultdict(list)

            for group in groups:

                groups_lookup[group.subsession_id].append(group.id)

            players_to_create = []

            for ss_id, ss_rd in subsessions:
                roles = get_roles(Constants)
                participant_index = 0
                for group_id in groups_lookup[ss_id]:
                    for id_in_group in range(1, ppg + 1):
                        participant = participant_values[participant_index]
                        players_to_create.append(
                            Player(
                                session=session,
                                subsession_id=ss_id,
                                round_number=ss_rd,
                                participant_id=participant[0],
                                group_id=group_id,
                                id_in_group=id_in_group,
                                _role=get_role(roles, id_in_group),
                            )
                        )
                        participant_index += 1

            # Create players
            db.add_all(players_to_create)

        dbq(Participant).filter_by(session=session).update(
            {Participant._max_page_index: num_pages}
        )

        for subsession in session.get_subsessions():
            target = subsession.get_user_defined_target()
            func = getattr(target, 'creating_session', None)
            if func:
                func(subsession)

        session._set_admin_report_app_names()

        if room_name is not None:
            from otree.room import ROOM_DICT

            room = ROOM_DICT[room_name]
            room.set_session(session)

        db.commit()
        return session
    except Exception:
        # another way would be to look into nested transactions,
        # but this seems simpler.
        db.delete(session)
        raise


class CreateSessionError(Exception):
    pass


def create_session_traceback_wrapper(**kwargs):
    '''
    catch it at an inner level,
    so we can give smaller tracebacks on 'creating session' page
    '''
    try:
        return create_session(**kwargs)
    except Exception as exc:
        raise CreateSessionError from exc
