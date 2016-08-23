# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0011_auto_20160805_1735'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='participant',
            options={'ordering': ['pk']},
        ),
        migrations.AlterModelOptions(
            name='session',
            options={'ordering': ['pk']},
        ),
        migrations.AlterIndexTogether(
            name='participant',
            index_together=set([('session', 'mturk_worker_id', 'mturk_assignment_id')]),
        ),
    ]
