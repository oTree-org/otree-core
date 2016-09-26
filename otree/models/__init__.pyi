from typing import List, Union, Any
from otree.common import Currency, RealWorldCurrency



class Session:

    config = None  # type: dict
    vars = None  # type: dict
    def get_participants(self) -> List['Participant']: pass
    def get_subsessions(self) -> List['Subsession']: pass

class Participant:

    session = None # type: Session
    vars = None  # type: dict
    label = None  # type: str
    id_in_session = None  # type: int
    payoff = None  # type: Currency

    def get_players(self) -> List['Player']: pass
    def payoff_plus_participation_fee(self) -> RealWorldCurrency: pass


class BaseSubsession:

    session = None # type: Session
    round_number = None  # type: int

    def get_groups(self) -> List['Group']: pass
    def get_group_matrix(self) -> List[List['Player']]: pass
    def set_group_matrix(
            self,
            group_matrix: Union[List[List['Player']],List[List[int]]]): pass
    def get_players(self) -> List['Player']: pass
    def in_previous_rounds(self) -> List['Subsession']: pass
    def in_all_rounds(self) -> List['Subsession']: pass
    def before_session_starts(self): pass
    def in_round(self, round_number) -> 'Subsession': pass
    def in_rounds(self, first, last) -> List['Subsession']: pass
    def group_like_round(self, round_number: int): pass
    def group_randomly(self, fixed_id_in_group: bool=False): pass

class BaseGroup:

    session = None # type: Session
    subsession = None  # type: Subsession
    round_number = None  # type: int

    def set_players(self, players_list: List['Player']): pass
    def get_players(self) -> List['Player']: pass
    def get_player_by_role(self, role) -> 'Player': pass
    def get_player_by_id(self, id_in_group) -> 'Player': pass
    def in_previous_rounds(self) -> List['Group']: pass
    def in_all_rounds(self) -> List['Group']: pass
    def in_round(self, round_number) -> 'Group': pass
    def in_rounds(self, first: int, last: int) -> List['Group']: pass


class BasePlayer:

    id_in_group = None  # type: int
    payoff = None  # type: Currency
    participant = None  # type: Participant
    session = None # type: Session
    group = None  # type: Group
    subsession = None  # type: Subsession
    round_number = None  # type: int

    def in_previous_rounds(self) -> List['Player']: pass
    def in_all_rounds(self) -> List['Player']: pass
    def get_others_in_group(self) -> List['Player']: pass
    def get_others_in_subsession(self) -> List['Player']: pass
    def role(self) -> str: pass
    def in_round(self, round_number) -> 'Player': pass
    def in_rounds(self, first, last) -> List['Player']: pass

Subsession = Union[BaseSubsession, Any]
Group = Union[BaseGroup]
Player = Union[BasePlayer, Any]
