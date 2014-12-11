#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from flake8 import engine

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.conf import settings


class TestStyle(TestCase):

    def setUp(self):
        self.quiet = settings.TEST_VERBOSITY <= 2
        self.pep8 = engine.get_style_guide(quiet=self.quiet)
        for path in settings.PEP8_CHECK:
            if not os.path.isdir(path) and not os.path.isfile(path):
                msg = "'{}' is not file and is not dir".format(path)
                raise ImproperlyConfigured(msg)
            self.pep8.paths.append(path)

    def test_pep8(self):
        result = self.pep8.check_files()
        error_q = result.total_errors
        if error_q:
            lines = ["Found '{}' pep8-style errors.".format(error_q)]
            lines.append(
                "Please check the Python code style reference: "
                "https://www.python.org/dev/peps/pep-0008/"
            )
            lines.append("Here is a resume of errors found: ")
            lines.extend(result.get_statistics())
            if self.quiet:
                lines.append(
                    "For a more acurate description run "
                    "the test with verbosity > 2"
                )
            self.fail("\n".join(lines))

