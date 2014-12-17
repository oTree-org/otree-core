#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import multiprocessing
import collections

from flake8 import engine, reporter

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from django.conf import settings


# =============================================================================
# CONSTANTS
# =============================================================================

CHECK = settings.PEP8.get("check", ())

EXCLUDE = list(settings.PEP8.get("exclude", ()))


# =============================================================================
# REPORT
# =============================================================================

class FileCollectReport(reporter.QueueReport):

    def __init__(self, *args, **kwargs):
        super(FileCollectReport, self).__init__(*args, **kwargs)
        self._ferrs_queue = multiprocessing.Queue()
        self._files_with_errors = collections.defaultdict(list)

    def error(self, line_number, offset, text, check):
        super(FileCollectReport, self).error(line_number, offset, text, check)
        self._ferrs_queue.put((self.filename, line_number))

    def get_statistics(self):
        stats = super(FileCollectReport, self).get_statistics()
        if stats:
            stats.append("\nFiles with errors:")
            for filename, linenos in self.files_with_errors():
                lines = ", ".join(map(str, linenos))
                line = u"{} - Lines: {}".format(filename, lines)
                stats.append(line)
        return stats

    def files_with_errors(self):
        while self._ferrs_queue.qsize():
            filename, line_number = self._ferrs_queue.get_nowait()
            self._files_with_errors[filename].append(line_number)
        return tuple(self._files_with_errors.items())


# =============================================================================
# TEST
# =============================================================================

class TestStyle(TestCase):

    def setUp(self):
        self.quiet = settings.TEST_VERBOSITY <= 2
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
            lines = ["Found '{}' pep8-style errors.".format(error_q)]
            lines.append(
                "Please check the Python code style reference: "
                "https://www.python.org/dev/peps/pep-0008/"
            )
            lines.append("\nHere is a resume of errors found: ")
            lines.extend(report.get_statistics())
            self.fail("\n".join(lines))
