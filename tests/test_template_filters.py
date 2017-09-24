import random
import decimal
import string

from django.utils import html
from django.template import Context, Template
from django.contrib.staticfiles.storage import staticfiles_storage

import six

from unittest import mock

from otree.common import Currency as c

from .utils import TestCase


class TestFilters(TestCase):

    def parse(self, fragment):
        return Template('{% load otree %}' + fragment)

    def render(self, fragment, context=None):
        if context is None:
            context = Context()
        if not isinstance(context, Context):
            context = Context(context)
        return self.parse(fragment).render(context)

    def test_monkey_patch_staticfiles_tag(self):
        with mock.patch.object(staticfiles_storage, "url") as url:
            self.render("{% load staticfiles %}{% static 'foo.jpg' %}")
            url.assert_called_once_with("foo.jpg")
        with mock.patch.object(staticfiles_storage, "url") as url:
            url.side_effect = ValueError("boom")
            with self.assertRaises(ValueError):
                self.render("{% load staticfiles %}{% static 'foo.jpg' %}")

    def test_abs_value(self):
        for value in [0, 1, random.random(), c(1)]:
            actual = self.render("{{value|abs}}", context={'value': value})
            expected = six.text_type(value)
            self.assertEquals(actual, expected)

            nvalue = -value
            expected = self.render("{{value|abs}}", context={'value': nvalue})
            self.assertEquals(actual, expected)

        with self.assertRaises(TypeError):
            self.render("{{value|abs}}", context={'value': "foo"})
        with self.assertRaises(TypeError):
            self.render("{{value|abs}}", context={'value': None})

    def test_currency_filter(self):
        with self.settings(USE_POINTS=False, REAL_WORLD_CURRENCY_CODE='USD'):
            self.assertEqual(
                self.render('{{1|c}}'),
                '$1.00'
            )

    def test_json(self):
        for python_input, expected_output in [
            (None, 'null'),
            (c(1), '1.0'),
            ("hi", '"hi"'),
            ({"a": 1}, '{"a": 1}')
        ]:
            output = self.render("{{value|json}}", context={'value': python_input})
            self.assertEquals(output, expected_output)