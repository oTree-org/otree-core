# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0021_auto_20170719_2320'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='session',
            name='mturk_qualification_type_id',
        ),
    ]
