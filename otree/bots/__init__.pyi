from typing import Any, List
from otree.common import Currency, RealWorldCurrency

## This code is duplicated in several places
# bots/__init__.pyi, views/__init__.pyi, models/__init__.pyi
# importing doesn't seem to work with PyCharm autocomplete

class Session:

    config = None  # type: dict
    vars = None  # type: dict
    def get_participants(self) -> List[Participant]: pass

    # we could make it List[Subsession] but then we have to define Subsession
    # somewhere, because importing doesn't seem to work for pyi autocomplete
    # in pycharm. too much effort for a rarely used method
    def get_subsessions(self) -> List: pass

class Participant:

    session = None # type: Session
    vars = None  # type: dict
    label = None  # type: str
    id_in_session = None  # type: int
    payoff = None  # type: Currency

    # see comment above about importing
    def get_players(self) -> List: pass
    def payoff_plus_participation_fee(self) -> RealWorldCurrency: pass


class Bot:
    html = '' # type: str
    case = None # type: Any
    cases = [] # type: List
    participant = None  # type: Participant
    session = None # type: Participant

def Submission(PageClass, post_data: dict={}, *, check_html=True, timeout_happened=False): pass
def SubmissionMustFail(PageClass, post_data: dict={}, *, check_html=True): pass