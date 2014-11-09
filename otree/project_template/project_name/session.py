from otree.session import SessionType
from otree.common import Currency as c

def session_types():
    return [
        SessionType(
            name="My App",
            fixed_pay=c(0),
            num_bots=12,
            num_demo_participants=2,
            subsession_apps=[
                'myapp',
            ],
            doc="""
            Description of this session type.
            """
        ),
    ]

def show_on_demo_page(session_type_name):
    return True

demo_page_intro_text = 'Click on one of the below sessions to play.'