# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import otree.db.models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0002_auto_20160526_1408'),
    ]

    operations = [
        migrations.AddField(
            model_name='failedsessioncreation',
            name='message',
            field=otree.db.models.CharField(null=True, max_length=300),
        ),
        migrations.AlterField(
            model_name='roomsession',
            name='room_name',
            field=otree.db.models.CharField(max_length=255, unique=True, null=True),
        ),
    ]
