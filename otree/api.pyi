from typing import Union, List, Any, Optional

from otree.currency import RealWorldCurrency, Currency

class Currency(Currency):
    '''
    PyCharm autocomplete seems to require that I explicitly define the class in this file
    (if I import, it says the reference to Currency is not found)
    '''

def currency_range(first, last, increment) -> List[Currency]:
    pass


# mocking the public API for PyCharm autocomplete.
# one downside is that PyCharm doesn't seem to fully autocomplete arguments
# in the .pyi. It gives the yellow pop-up, but doesn't complete what you
# are typing. (2017-07-01: seems to work in PyCharm 2017.1.4?)
class models:

    '''
    The code in this class has nothing to do with implementation,
    but rather defines the interface for model fields,
    so that pyCharm autocompletes them properly.

    It defines their __init__ so that when instantiating the class,
    PyCharm suggests the right arguments.
    Apart from that, they can be used as the equivalent Python data type
    (e.g. BooleanField is a bool, CharField is str)

    Without inheriting from bool, str, etc., PyCharm flags certain usages in yellow,
    like:

        c(1) + c(1)

    Results in: "Currency does not define __add__, so the + operator cannot
    be used on its instances"

    If "a" is a CurrencyField, then
        self.a + c(1)

    PyCharm warns: 'Currency does not define __add__, so the + operator cannot
    be used on its instances'

        c(1) + 1

    'Expected type "int", got "Currency" instead'

        self.a + 1

    'Expected type "int", got "CurrencyField" instead'


    '''

    def __getattr__(self, item):
        pass
    class BooleanField(bool):
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            label=None,
            doc='',
            blank=False,
            **kwargs
        ):
            pass
    class StringField(str):
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            label=None,
            doc='',
            max_length=10000,
            blank=False,
            **kwargs
        ):
            pass
    class LongStringField(str):
        def __init__(
            self,
            *,
            initial=None,
            label=None,
            doc='',
            max_length=None,
            blank=False,
            **kwargs
        ):
            pass
    # need to copy-paste the __init__ between
    # Integer, Float, and Currency
    # because if I use inheritance, PyCharm doesn't auto-complete
    # while typing args
    class IntegerField(int):
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            label=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            **kwargs
        ):
            pass
    class FloatField(float):
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            label=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            **kwargs
        ):
            pass
    class CurrencyField(Currency):
        def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            label=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            **kwargs
        ):
            pass
    class Link:
        def __init__(self, to):
            pass

class widgets:
    def __getattr__(self, item):
        pass
    # don't need HiddenInput because you can just write <input type="hidden" ...>
    # and then you know the element's selector
    class CheckboxInput:
        pass
    class RadioSelect:
        pass
    class RadioSelectHorizontal:
        pass

class Session:

    config: dict
    vars: dict
    num_participants: int
    def get_participants(self) -> List[Participant]:
        pass
    def get_subsessions(self) -> List[BaseSubsession]:
        pass

class Participant:

    session: Session
    vars: dict
    label: str
    id_in_session: int
    payoff: Currency
    def get_players(self) -> List[BasePlayer]:
        pass
    def payoff_plus_participation_fee(self) -> RealWorldCurrency:
        pass

class BaseConstants:
    pass

class BaseSubsession:

    session: Session
    round_number: int
    def get_groups(self) -> List[BaseGroup]:
        pass
    def get_group_matrix(self) -> List[List[BasePlayer]]:
        pass
    def set_group_matrix(
        self, group_matrix: Union[List[List[BasePlayer]], List[List[int]]]
    ):
        pass
    def get_players(self) -> List[BasePlayer]:
        pass
    def in_previous_rounds(self) -> List[BaseSubsession]:
        pass
    def in_all_rounds(self) -> List[BaseSubsession]:
        pass
    def creating_session(self):
        pass
    def in_round(self, round_number) -> BaseSubsession:
        pass
    def in_rounds(self, first, last) -> List[BaseSubsession]:
        pass
    def group_like_round(self, round_number: int):
        pass
    def group_randomly(self, fixed_id_in_group: bool = False):
        pass
    def vars_for_admin_report(self):
        pass
    def group_by_arrival_time_method(self, waiting_players):
        pass
    # this is so PyCharm doesn't flag attributes that are only defined on the app's Subsession,
    # not on the BaseSubsession
    def __getattribute__(self, item):
        pass

class BaseGroup:

    session: Session
    subsession: BaseSubsession
    round_number: int
    def get_players(self) -> List[BasePlayer]:
        pass
    def get_player_by_role(self, role) -> BasePlayer:
        pass
    def get_player_by_id(self, id_in_group) -> BasePlayer:
        pass
    def in_previous_rounds(self) -> List[BaseGroup]:
        pass
    def in_all_rounds(self) -> List[BaseGroup]:
        pass
    def in_round(self, round_number) -> BaseGroup:
        pass
    def in_rounds(self, first: int, last: int) -> List[BaseGroup]:
        pass
    def __getattribute__(self, item):
        pass

class BasePlayer:

    id_in_group: int
    payoff: Currency
    participant: Participant
    session: Session
    group: BaseGroup
    subsession: BaseSubsession
    round_number: int
    role: str
    def start(self):
        pass
    def in_previous_rounds(self) -> List[BasePlayer]:
        pass
    def in_all_rounds(self) -> List[BasePlayer]:
        pass
    def get_others_in_group(self) -> List[BasePlayer]:
        pass
    def get_others_in_subsession(self) -> List[BasePlayer]:
        pass
    def in_round(self, round_number) -> BasePlayer:
        pass
    def in_rounds(self, first, last) -> List[BasePlayer]:
        pass
    def __getattribute__(self, item):
        pass

class ExtraModel:
    pass

class WaitPage:
    wait_for_all_groups = False
    group_by_arrival_time = False
    title_text: str
    body_text: str
    template_name: str
    after_all_players_arrive: str
    round_number: int
    participant: Participant
    session: Session
    def is_displayed(self):
        pass
    def js_vars(self):
        pass
    def vars_for_template(self):
        pass
    def app_after_this_page(self, upcoming_apps):
        pass

class Page:
    round_number: int
    template_name: str
    timeout_seconds: int
    timeout_happened: bool
    timer_text: str
    participant: Participant
    session: Session
    form_model: str
    form_fields: List[str]
    live_method: str
    def get_form_fields(self):
        pass
    def vars_for_template(self):
        pass
    def js_vars(self):
        pass
    def before_next_page(self):
        pass
    def is_displayed(self):
        pass
    def error_message(self, values):
        pass
    def get_timeout_seconds(self):
        pass
    def app_after_this_page(self, upcoming_apps):
        pass


class Bot:
    html: str
    case: Any
    cases: List
    participant: Participant
    session: Participant
    round_number: int

def Submission(
    PageClass, post_data: dict = {}, *, check_html=True, timeout_happened=False
):
    pass

def SubmissionMustFail(
    PageClass, post_data: dict = {}, *, check_html=True, error_fields=[]
):
    pass

def expect(*args):
    pass
