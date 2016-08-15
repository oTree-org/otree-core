from otree.models import Participant
from typing import Any

class Bot:
    html = None # type: str
    case = None # type: Any
    participant = None  # type: Participant
    session = None # type: Participant

def Submission(PageClass, post_data: dict={}, check_html=True): pass
def SubmissionMustFail(PageClass, post_data: dict={}, check_html=True): pass