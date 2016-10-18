from __future__ import division

from otree.api import Bot, SubmissionMustFail

from . import views
from .models import Constants
from django.conf import settings
from collections import namedtuple

LocStrings = namedtuple(
    'LocStrings',
    ['form_has_errors', 'next', 'yes', 'time_left', 'user_defined_string'])


STRINGS = {
    'de': LocStrings(
        form_has_errors='Bitte korrigieren',
        next='Weiter',
        yes='Ja',
        time_left='Verbleibende Zeit',
        user_defined_string='Fußball'
    ),
    'zh-hans': LocStrings(
        form_has_errors='请修复',
        next='下一页',
        yes='是',
        time_left='时间',
        user_defined_string='足球'
    ),
}

class PlayerBot(Bot):

    def play_round(self):
        strings = STRINGS[settings.LANGUAGE_CODE]
        assert strings.next in self.html
        assert strings.yes in self.html
        assert strings.time_left in self.html
        assert strings.user_defined_string in self.html
        yield SubmissionMustFail(views.Page1)
        assert strings.form_has_errors in self.html
