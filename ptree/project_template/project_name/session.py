from ptree.session import SessionType

def session_types():
    return [
        SessionType(
            name="My App",
            base_pay=0,
            session_participanRENAMEts_per_session=12,
            session_participanRENAMEts_per_demo_session=2,
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