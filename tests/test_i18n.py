from otree.session import create_session
from .utils import TestCase
from otree.bots.runner import run_bots
from django.test import override_settings

class TestI18N(TestCase):
    def setUp(self):
        self.session = create_session('i18n', num_participants=1)

    @override_settings(LANGUAGE_CODE='de')
    def test_german(self):
        run_bots(self.session)

    @override_settings(LANGUAGE_CODE='zh-hans')
    def test_chinese(self):
        run_bots(self.session)
