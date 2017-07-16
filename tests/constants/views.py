from . import models
from otree.api import WaitPage
from tests.utils import BlankTemplatePage as Page
from .models import Constants


class Page1(Page):
    pass


page_sequence = [
    Page1,
]
