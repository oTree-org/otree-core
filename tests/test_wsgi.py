#!/usr/bin/env python
# -*- coding: utf-8 -*-

from whitenoise.django import DjangoWhiteNoise

from otree import wsgi

from .base import TestCase


class TestWSGI(TestCase):

    def test_app(self):
        self.assertIsInstance(wsgi.application, DjangoWhiteNoise)
