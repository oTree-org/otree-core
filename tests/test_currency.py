import random
from django.template import Template, Context
from otree.common import Currency as c
from django.test import override_settings
from .utils import TestCase
import copy
import pickle
from decimal import Decimal
from operator import floordiv
from operator import truediv
from otree.currency import Currency
from unittest.mock import patch

import six


class CurrencyTests(TestCase):

    def test_create(self):
        assert Currency(3) == Decimal('3')

        assert Currency(3.14) == Decimal('3.14')
        assert Currency(3.141) == Decimal('3.14')
        assert Currency(3.145) == Decimal('3.15')

        assert Currency('3.14') == Decimal('3.14')
        assert Currency('3.141') == Decimal('3.14')
        assert Currency('3.145') == Decimal('3.15')

        assert Currency(Decimal('3.14')) == Decimal('3.14')
        assert Currency(Decimal('3.141')) == Decimal('3.14')
        assert Currency(Decimal('3.145')) == Decimal('3.15')

    def test_str(self):
        with self.settings(USE_POINTS=False):
            with self.settings(REAL_WORLD_CURRENCY_CODE='USD'):
                # should truncate
                self.assertEqual(str(Currency(3.141)), '$3.14')
                self.assertEqual(str(Currency(3.00)), '$3.00')
            with self.settings(REAL_WORLD_CURRENCY_CODE='EUR'):
                self.assertEqual(str(Currency(3.14)), '€3.14')
                self.assertEqual(str(Currency(3.00)), '€3.00')
            with self.settings(
                    REAL_WORLD_CURRENCY_CODE='USD',
                    REAL_WORLD_CURRENCY_DECIMAL_PLACES=3):
                self.assertEqual(str(Currency(3.141)), '$3.141')
        with self.settings(USE_POINTS=True):
            self.assertEqual(str(Currency(3)), '3 points')
            with self.settings(POINTS_DECIMAL_PLACES=2):
                self.assertEqual(str(Currency(3)), '3.00 points')
            with self.settings(POINTS_CUSTOM_NAME='tokens'):
                self.assertEqual(str(Currency(3)), '3 tokens')

    def test_currency_non_ascii_character(self):
        # https://github.com/oTree-org/otree-core/issues/387
        with self.settings(REAL_WORLD_CURRENCY_CODE='EUR', USE_POINTS=False):
            value = Currency(1)
            template = Template('''{{money}}''')
            ctx = Context({"money": c(1)})
            rendered = template.render(ctx)
            self.assertIn('€', rendered)
            self.assertEquals(rendered, six.text_type(value))

    def test_format(self):
        with self.settings(USE_POINTS=False, REAL_WORLD_CURRENCY_CODE='USD'):
            pi = Currency(3.14)
            assert '{}'.format(pi) == '$3.14'
            assert '{:s}'.format(pi) == '$3.14'
            assert isinstance(u'{}'.format(pi), six.text_type)
            assert '{:.1f}'.format(pi) == '3.1'
            assert '{:e}'.format(pi) == '3.14e+0'

    def test_repr(self):
        pi = Currency('3.14')
        assert repr(pi) == 'Currency(3.14)'

    def test_arithmetic(self):
        pi = Currency(3.14)
        e = Currency(2.78)

        # NOTE: we test this way to check that bools are returned
        assert (pi == 3.14) is True
        assert (pi == Decimal('3.14')) is True
        assert (pi == 3) is False
        assert (pi != 3) is True
        assert (Currency(3) == 3) is True

        assert (3 == pi) is False
        assert (3 != pi) is True

        assert pi + e == 5.92
        assert pi - e == 0.36

        assert -pi == -3.14
        assert +pi == 3.14
        assert abs(pi) == 3.14
        assert abs(-pi) == 3.14


    def test_pow(self):
        m = Currency(2)
        assert m ** 7 == 128
        assert pow(m, 7, 3) == 2


    def test_arithmetic_returns_money_instance(self):
        assert type(Currency(3) + 2) is Currency
        assert type(3 + Currency(2)) is Currency
        assert type(Currency(3) - 2) is Currency
        assert type(3 - Currency(2)) is Currency
        assert type(Currency(3) * 2) is Currency
        assert type(3 * Currency(2)) is Currency
        assert type(floordiv(Currency(3), 2)) is Currency
        assert type(floordiv(3, Currency(2))) is Currency
        assert type(truediv(Currency(3), 2)) is Currency
        assert type(truediv(3, Currency(2))) is Currency
        assert type(Currency(3) ** 2) is Currency
        assert type(2 ** Currency(3)) is Currency
        assert type(+Currency(2)) is Currency
        assert type(-Currency(2)) is Currency
        assert type(abs(Currency(2))) is Currency


    def test_precision(self):
        assert Currency(1000) * 1.001 == 1001
        assert Currency('1.001') * 1000 == 1000

    def test_higher_precision(self):
        with self.settings(USE_POINTS=False, REAL_WORLD_CURRENCY_DECIMAL_PLACES=3):
            assert Currency('1.001') * 1000 == 1001


    def test_int_arithmetic(self):
        pi = Currency(3.14)

        assert pi + 1 == 4.14
        assert pi - 1 == 2.14
        assert pi * 2 == 6.28
        assert pi / 3 == 1.05

        assert 1 + pi == 4.14
        assert 1 - pi == -2.14
        assert 2 * pi == 6.28
        assert 9 / pi == 2.87


    def test_float_arithmetic(self):
        pi = Currency(3.14)

        assert pi + 0.2 == 3.34
        assert pi - 0.2 == 2.94
        assert pi * 0.2 == 0.63
        assert pi / 1.5 == 2.09

        # We coerse to 2 digits before operation
        assert pi + 0.005 == 3.15
        assert pi - 0.005 == 3.13


    def test_hashing(self):
        x = {Currency(3): 1}

    def test_copy(self):
        pi = Currency(3.14)
        assert pi == copy.copy(pi)
        assert pi == copy.deepcopy(pi)

    def test_pickle(self):
        pi = Currency(3.14)
        assert pickle.loads(pickle.dumps(pi)) == pi
        assert pickle.loads(pickle.dumps(pi, -1)) == pi

    def test_currency_unary_operator(self):
        #  https://github.com/oTree-org/otree-core/issues/391
        msg = "Currency operator '{}' fail"
        for money in [c(-random.random()), c(random.random()), c(0)]:
            self.assertIsInstance(abs(money), c, msg.format("abs()"))
            self.assertIsInstance(-money, c, msg.format("-VALUE"))
            self.assertIsInstance(+money, c, msg.format("+VALUE"))

    def test_currency_operator(self):
        msg = "Currency operator '{}' fail"
        for money in [c(-random.random()), c(random.random()), c(0)]:
            money = money + 1
            self.assertIsInstance(money, c, msg.format("+"))
            money = money - 1
            self.assertIsInstance(money, c, msg.format("-"))
            money = money / 1
            self.assertIsInstance(money, c, msg.format("/"))
            money = money * 1
            self.assertIsInstance(money, c, msg.format("*"))
            money = money ** 1
            self.assertIsInstance(money, c, msg.format("**"))
            money = money // 1
            self.assertIsInstance(money, c, msg.format("//"))

    def test_currency_inplace_operator(self):
        msg = "Currency operator '{}' fail"
        for money in [c(-random.random()), c(random.random()), c(0)]:
            money += 1
            self.assertIsInstance(money, c, msg.format("+="))
            money -= 1
            self.assertIsInstance(money, c, msg.format("-="))
            money /= 1
            self.assertIsInstance(money, c, msg.format("/="))
            money *= 1
            self.assertIsInstance(money, c, msg.format("*="))
            money **= 1
            self.assertIsInstance(money, c, msg.format("**="))
            money //= 1
            self.assertIsInstance(money, c, msg.format("//="))
