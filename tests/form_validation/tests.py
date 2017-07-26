from . import views
from otree.api import Bot, SubmissionMustFail, Currency as c
import random



class PlayerBot(Bot):

    def play_round(self):
        for PageClass in views.page_sequence:
            yields = PageClass.get_yields()
            for submission in yields[:-1]:
                yield SubmissionMustFail(PageClass, submission)
            yield PageClass, yields[-1]