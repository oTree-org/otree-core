# 2017-08-07: i temporarily disabled this feature
'''
from .base import TestCase
from tests.constants.models import Constants
from otree.constants import MustCopyError
import random

class TestConstants(TestCase):

    def test_setattr(self):
        with self.assertRaises(AttributeError):
            Constants.c_int += 1
        with self.assertRaises(AttributeError):
            Constants.new_attr = 1

    def test_mutate_list(self):

        self.assertEqual(Constants.c_list, [1,2])

        # block direct mutation
        with self.assertRaises(MustCopyError):
            Constants.c_list[0] = 10
        with self.assertRaises(MustCopyError):
            c_list_bad = Constants.c_list
            random.shuffle(c_list_bad)
        with self.assertRaises(MustCopyError):
            Constants.c_list.append(3)

        # make sure we didn't modify it
        self.assertEqual(Constants.c_list, [1,2])

        # read-only operations are OK
        e0 = Constants.c_list[0]
        e1 = Constants.c_list[:]
        l2 = Constants.c_list + [3]
        self.assertEqual(l2, [1, 2, 3])

        # after copying, should be a normal list
        c_copied = Constants.c_list.copy()
        self.assertEqual(type(c_copied), list)
        random.shuffle(c_copied)

        c_sliced = Constants.c_list[:]
        self.assertEqual(type(c_sliced), list)
        random.shuffle(c_sliced)
'''