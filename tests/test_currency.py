# -*- coding: utf-8 -*-

from django.template import Template, Context

import six

from otree.common import Currency as c

from .base import TestCase


class CurrencyTests(TestCase):

    def test_currency_non_ascii_character(self):
        # https://github.com/oTree-org/otree-core/issues/387

        class TestC(c):
            CODE = 'EUR'

        money = TestC(23)
        template = Template('''{{money}}''')
        ctx = Context({"money": money})
        rendered = template.render(ctx)
        self.assertEquals(rendered, six.text_type(money))
