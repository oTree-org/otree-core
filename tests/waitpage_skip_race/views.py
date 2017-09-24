from . import models
from otree.api import WaitPage
from tests.utils import BlankTemplatePage as Page
from .models import Constants


class Page1(Page):
    pass


class MyWait(WaitPage):
    def is_displayed(self):
        return self.player.id_in_group == 1


class Page2(Page):
    pass


page_sequence = [
    Page1,
    MyWait,
    Page2,
]
