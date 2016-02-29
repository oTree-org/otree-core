#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================
from __future__ import print_function, unicode_literals

import csv
import argparse
import logging
import itertools

from django.core.management.base import BaseCommand

from otree.models import Session


# =============================================================================
# LOGGER
# =============================================================================

logger = logging.getLogger('otree')



# =============================================================================
# COMMND
# =============================================================================

class Command(BaseCommand):
    help = ("List al available sessions")

    def handle(self, **options):
        rows = []
        for session in Session.objects.all():
            stype = session.session_type
            rows.append({
                "name": stype["display_name"],
                "code": session.code,
                "participants": str(session.participant_set.count()),
                "appsequence": ", ".join(stype["app_sequence"])
            })

        if rows:
            rows.insert(0, {
                "name": "Name", "code": "Code",
                "participants": "Participants", "appsequence": "App Sequence"})

            name_just = max(len(r["name"]) for r in rows) + 2
            code_just = max(len(r["code"]) for r in rows) + 2
            participants_just = max(len(r["participants"]) for r in rows) + 2
            appsequence_just = max(len(r["appsequence"]) for r in rows) + 2

            for idx, row in enumerate(rows):
                if idx == 1:
                    print(
                        "-" * name_just, "-" * code_just,
                        "-" * participants_just, "-" * appsequence_just)
                print(
                    row["name"].ljust(name_just),
                    row["code"].ljust(code_just),
                    row["participants"].ljust(participants_just),
                    row["appsequence"].ljust(appsequence_just))
        print("")
