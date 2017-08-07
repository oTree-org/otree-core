# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0016_auto_20161120_1843'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='session',
            name='time_scheduled',
        ),
        migrations.RemoveField(
            model_name='session',
            name='time_started',
        ),
    ]
