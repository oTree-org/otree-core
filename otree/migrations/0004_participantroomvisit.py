# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import otree.db.models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0003_auto_20160531_1446'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParticipantRoomVisit',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('room_name', otree.db.models.CharField(max_length=500, null=True)),
                ('participant_label', otree.db.models.CharField(max_length=500, null=True)),
                ('random_code', otree.db.models.CharField(max_length=20, null=True)),
            ],
            options={
                'db_table': 'otree_participantroomvisit',
            },
        ),
    ]
