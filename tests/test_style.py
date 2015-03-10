#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import multiprocessing

from flake8 import engine, reporter

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.conf import settings


# =============================================================================
# CONSTANTS
# =============================================================================

CHECK = settings.PEP8.get("check", ())

EXCLUDE = list(settings.PEP8.get("exclude", ()))

PRJ_DIR_LEN = len(settings.PRJ_DIR)

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
        if IS_WINDOWS:
            # WINDOWS UGLY AND HACKISH PATCH for flake 8 is based on
            # http://goo.gl/2b53SG
            sys.argv.append(".")
            self.pep8 = engine.get_style_guide(exclude=EXCLUDE, jobs=1)
        else:
            self.pep8 = engine.get_style_guide(exclude=EXCLUDE)

        self.pep8.reporter = FileCollectReport
        report = self.pep8.init_report(self.pep8.reporter)
        report.input_file = self.pep8.input_file
        self.pep8.runner = report.task_queue.put

        for path in CHECK:
            if not os.path.isdir(path) and not os.path.isfile(path):
                msg = "'{}' is not file and is not dir".format(path)
                raise ImproperlyConfigured(msg)
            self.pep8.paths.append(path)

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
            for error in report.error_list():
                if error.startswith("/") or error.startswith("\\"):
                    error = error[1:]
                lines.append(error)
            lines.append("Total: {}".format(error_q))
            self.fail("\n".join(lines))
