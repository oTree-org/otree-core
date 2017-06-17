from typing import List, Union
from otree.common import Currency, RealWorldCurrency

## This code is duplicated in several places
# bots/__init__.pyi, views/__init__.pyi, models/__init__.pyi
# importing doesn't seem to work with PyCharm autocomplete


class Session:

    config = None  # type: dict
    vars = None  # type: dict
    def get_participants(self) -> List[Participant]: pass
    def get_subsessions(self) -> List[BaseSubsession]: pass

class Participant:

    session = None # type: Session
    vars = None  # type: dict
    label = None  # type: str
    id_in_session = None  # type: int
    payoff = None  # type: Currency

    def get_players(self) -> List[BasePlayer]: pass
    def payoff_plus_participation_fee(self) -> RealWorldCurrency: pass


class BaseSubsession:

    session = None # type: Session
    round_number = None # type: int

    def get_groups(self) -> List[BaseGroup]: pass
    def get_group_matrix(self) -> List[List[BasePlayer]]: pass
    def set_group_matrix(
            self,
            group_matrix: Union[List[List[BasePlayer]],List[List[int]]]): pass
    def get_players(self) -> List[BasePlayer]: pass
    def in_previous_rounds(self) -> List['BaseSubsession']: pass
    def in_all_rounds(self) -> List['BaseSubsession']: pass
    def creating_session(self): pass
    def in_round(self, round_number) -> 'BaseSubsession': pass
    def in_rounds(self, first, last) -> List['BaseSubsession']: pass
    def group_like_round(self, round_number: int): pass
    def group_randomly(self, fixed_id_in_group: bool=False): pass
    def vars_for_admin_report(self): pass

    # this is so PyCharm doesn't flag attributes that are only defined on the app's Subsession,
    # not on the BaseSubsession
    def __getattribute__(self, item): pass

class BaseGroup:

    session = None # type: Session
    subsession = None  # type: BaseSubsession
    round_number = None  # type: int

    def set_players(self, players_list: List[BasePlayer]): pass
    def get_players(self) -> List[BasePlayer]: pass
    def get_player_by_role(self, role) -> BasePlayer: pass
    def get_player_by_id(self, id_in_group) -> BasePlayer: pass
    def in_previous_rounds(self) -> List['BaseGroup']: pass
    def in_all_rounds(self) -> List['BaseGroup']: pass
    def in_round(self, round_number) -> 'BaseGroup': pass
    def in_rounds(self, first: int, last: int) -> List['BaseGroup']: pass

    def __getattribute__(self, item): pass

class BasePlayer:

    id_in_group = None  # type: int
    payoff = None  # type: Currency
    participant = None  # type: Participant
    session = None # type: Session
    group = None  # type: BaseGroup
    subsession = None  # type: BaseSubsession
    round_number = None  # type: int

    def in_previous_rounds(self) -> List['BasePlayer']: pass
    def in_all_rounds(self) -> List['BasePlayer']: pass
    def get_others_in_group(self) -> List['BasePlayer']: pass
    def get_others_in_subsession(self) -> List['BasePlayer']: pass
    def role(self) -> str: pass
    def in_round(self, round_number) -> 'BasePlayer': pass
    def in_rounds(self, first, last) -> List['BasePlayer']: pass

    def __getattribute__(self, item): pass