#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string
import random
import warnings

from otree import deprecate

from .base import TestCase


class DeprecateTest(TestCase):

    def random_string(self):
        chars = list(string.letters + string.digits)
        idx = random.randint(5, len(chars) - 1)
        random.shuffle(chars)
        return random.choice(string.letters) + "".join(chars[:idx])

    def extract_otree_dwarn(self, l):
        for w in l:
            if w.category == deprecate.OTreeDeprecationWarning:
                return w

    def test_dmessage(self):

        def create_random_object():
            name = self.random_string()
            return type(name, (), {}), name

        obj, name = create_random_object()
        msg = deprecate.MSG_TPL.format(name=name)
        self.assertEqual(msg, deprecate.dmessage(obj))

        obj, name = create_random_object()
        alt = self.random_string()
        msg = deprecate.MSG_ALTERNATIVE_TPL.format(name=name, alternative=alt)
        self.assertEqual(msg, deprecate.dmessage(obj, alt))

    def test_deprecated(self):

        @deprecate.deprecated()
        def dfunction():
            pass

        msg = deprecate.dmessage(dfunction)
        with warnings.catch_warnings(record=True) as warns:
            dfunction()
            dw = self.extract_otree_dwarn(warns)
            self.assertTrue(dw)
            self.assertEqual(dw.message.message, msg)

        alternative = self.random_string()

        @deprecate.deprecated(alternative)
        def dfunction():
            pass

        msg = deprecate.dmessage(dfunction, alternative)
        with warnings.catch_warnings(record=True) as warns:
            dfunction()
            dw = self.extract_otree_dwarn(warns)
            self.assertTrue(dw)
            self.assertEqual(dw.message.message, msg)

    def test_dwarning(self):

        with warnings.catch_warnings(record=True) as warns:
            msg = self.random_string()
            deprecate.dwarning(msg)
            dw = self.extract_otree_dwarn(warns)
            self.assertTrue(dw)
            self.assertEqual(dw.message.message, msg)

        with warnings.catch_warnings(record=True) as warns:
            warnings.simplefilter("ignore", deprecate.OTreeDeprecationWarning)
            msg = self.random_string()
            deprecate.dwarning(msg)
            dw = self.extract_otree_dwarn(warns)
            self.assertFalse(dw)

        with warnings.catch_warnings(record=True) as warns:
            warnings.simplefilter("error", deprecate.OTreeDeprecationWarning)
            msg = self.random_string()
            with self.assertRaises(deprecate.OTreeDeprecationWarning) as cm:
                deprecate.dwarning(msg)
            self.assertEqual(cm.exception.message, msg)
