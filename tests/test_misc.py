import otree

from .base import TestCase


class TestOtreePackage(TestCase):

    def test_get_version(self):
        self.assertEquals(otree.get_version(), otree.__version__)
