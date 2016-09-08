# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0012_auto_20160821_2339'),
    ]

    operations = [
        migrations.AddField(
            model_name='failedsessioncreation',
            name='traceback',
            field=models.TextField(default=''),
        ),
    ]
