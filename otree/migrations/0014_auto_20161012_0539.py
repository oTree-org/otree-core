# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0013_failedsessioncreation_traceback'),
    ]

    operations = [
        migrations.RenameField(
            model_name='completedgroupwaitpage',
            old_name='after_all_players_arrive_run',
            new_name='fully_completed',
        ),
        migrations.RenameField(
            model_name='completedsubsessionwaitpage',
            old_name='after_all_players_arrive_run',
            new_name='fully_completed',
        ),
    ]
