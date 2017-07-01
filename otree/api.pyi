from typing import Union, List, Any
from otree.common import RealWorldCurrency

class Currency:
    def __init__(self, *args):
        pass

    def to_real_world_currency(self, session): pass

def currency_range(first, last, increment) -> List[Currency]: pass
def safe_json(obj): pass


# mocking the public API for PyCharm autocomplete.
# one downside is that PyCharm doesn't seem to fully autocomplete arguments
# in the .pyi. It gives the yellow pop-up, but doesn't complete what you
# are typing. (2017-07-01: seems to work in PyCharm 2017.1.4?)
class models:

    def __getattr__(self, item):
        pass

    class BooleanField(object):
        def __init__(
                self,
                *,
                choices=None,
                widget=None,
                initial=None,
                verbose_name=None,
                doc='',
                null=True,
                help_text='',
                **kwargs):
            pass

    class CharField(object):
        def __init__(
                self,
                *,
                choices=None,
                widget=None,
                initial=None,
                verbose_name=None,
                doc='',
                max_length=10000,
                blank=False,
                null=True,
                help_text='',
                **kwargs):
            pass

    # need to copy-paste the __init__ between
    # PositiveInteger, Integer, Float, and Currency
    # because if I use inheritance, PyCharm doesn't auto-complete
    # while typing args

    class PositiveIntegerField:
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            verbose_name=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            null=True,
            help_text='',
            **kwargs):
                pass

    class IntegerField:
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            verbose_name=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            null=True,
            help_text='',
            **kwargs):
                pass

    class FloatField:
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            verbose_name=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            null=True,
            help_text='',
            **kwargs):
                pass

    class CurrencyField:
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            verbose_name=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            null=True,
            help_text='',
            **kwargs):
                pass

    class TextField:
        pass


class widgets:
    def __getattr__(self, item):
        pass

    class HiddenInput: pass
    class CheckboxInput: pass
    class Select: pass
    class RadioSelect: pass
    class RadioSelectHorizontal: pass
    class SliderInput: pass


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


class BaseConstants: pass


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


class WaitPage:
    wait_for_all_groups = False
    group_by_arrival_time = False
    title_text = None
    body_text = None
    template_name = None
    round_number = None  # type: int
    participant = None  # type: Participant
    session = None  # type: Session

    def is_displayed(self) -> bool: pass
    def after_all_players_arrive(self): pass
    def get_players_for_group(self, waiting_players): pass


class Page:
    round_number = None  # type: int
    template_name = None # type: str
    timeout_seconds = None # type: int
    timeout_submission = None # type: dict
    timeout_happened = None # type: bool
    timer_text = None # type: str
    participant = None  # type: Participant
    session = None  # type: Session
    form_model = None #
    form_fields = None  # type: List[str]

    def get_form_fields(self) -> List['str']: pass
    def vars_for_template(self) -> dict: pass
    def before_next_page(self): pass
    def is_displayed(self) -> bool: pass
    def error_message(self, values): pass
    def get_timeout_seconds(self): pass


class Bot:
    html = '' # type: str
    case = None # type: Any
    cases = [] # type: List
    participant = None  # type: Participant
    session = None # type: Participant

def Submission(PageClass, post_data: dict={}, *, check_html=True, timeout_happened=False): pass
def SubmissionMustFail(PageClass, post_data: dict={}, *, check_html=True): pass
