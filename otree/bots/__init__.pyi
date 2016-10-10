from typing import Any, List
from otree.common import Currency, RealWorldCurrency

## This code is duplicated in several places
# bots/__init__.pyi, views/__init__.pyi, models/__init__.pyi
# importing doesn't seem to work with PyCharm autocomplete

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


class Bot:
    html = '' # type: str
    case = None # type: Any
    cases = [] # type: List
    participant = None  # type: Participant
    session = None # type: Participant

def Submission(PageClass, post_data: dict={}, *, check_html=True): pass
def SubmissionMustFail(PageClass, post_data: dict={}, *, check_html=True): pass