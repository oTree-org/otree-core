#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import multiprocessing
import unittest

from flake8 import engine, reporter

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.conf import settings


# =============================================================================
# CONSTANTS
# =============================================================================

CHECK = settings.PEP8.get("check", ())

EXCLUDE = list(settings.PEP8.get("exclude", ()))

PRJ_DIR_LEN = len(settings.PRJ_DIR) + 1

IS_WINDOWS = sys.platform.startswith("win")


# =============================================================================
# REPORT
# =============================================================================

class FileCollectReport(reporter.QueueReport):

    def __init__(self, *args, **kwargs):
        super(FileCollectReport, self).__init__(*args, **kwargs)
        self._errs_queue = multiprocessing.Queue()
        self._errors = []

    def error(self, line_number, offset, text, check):
        super(FileCollectReport, self).error(line_number, offset, text, check)
        self._errs_queue.put((self.filename, line_number, offset, text))

    def error_list(self):
        while self._errs_queue.qsize():
            filepath, line_number, offset, text = self._errs_queue.get_nowait()
            filename = filepath[PRJ_DIR_LEN:]
            error = u"{}:{}:{}: {}".format(filename, line_number, offset, text)
            self._errors.append(error)
        return tuple(self._errors)


# =============================================================================
# TEST
# =============================================================================

class TestStyle(TestCase):

    def setUp(self):
        self.quiet = settings.TEST_VERBOSITY <= 2
        self.pep8 = engine.get_style_guide(exclude=EXCLUDE)
        self.pep8.n_jobs = 1
        self.pep8.reporter = FileCollectReport
        report = self.pep8.init_report(self.pep8.reporter)
        report.input_file = self.pep8.input_file
        self.pep8.runner = report.task_queue.put

        for path in CHECK:
            if not os.path.isdir(path) and not os.path.isfile(path):
                msg = "'{}' is not file and is not dir".format(path)
                raise ImproperlyConfigured(msg)
            self.pep8.paths.append(path)

    @unittest.skipUnless(not IS_WINDOWS, "not work on Windows")
    def test_pep8(self):
        report = self.pep8.check_files()
        error_q = report.total_errors
        if error_q:
            lines = ["Found pep8-style errors."]
            lines.append(
                "Please check the Python code style reference: "
                "https://www.python.org/dev/peps/pep-0008/"
            )
            lines.append("\nErrors found: ")
            lines.extend(report.error_list())
            lines.append("Total: {}".format(error_q))
            self.fail("\n".join(lines))
