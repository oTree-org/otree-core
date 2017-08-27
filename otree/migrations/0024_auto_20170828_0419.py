# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0023_auto_20170813_1511'),
    ]

    operations = [
        migrations.AlterField(
            model_name='participantroomvisit',
            name='last_updated',
            field=models.FloatField(),
        ),
    ]
