# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import otree.db.models
import otree.common_internal


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0005_auto_20160601_1324'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExpectedRoomParticipant',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('room_name', otree.db.models.CharField(max_length=500, null=True)),
                ('participant_label', otree.db.models.CharField(max_length=500, null=True)),
            ],
            options={
                'db_table': 'otree_expectedroomparticipant',
            },
        ),
        migrations.AlterField(
            model_name='participant',
            name='code',
            field=otree.db.models.CharField(max_length=16, null=True, default=otree.common_internal.random_chars_8, unique=True),
        ),
        migrations.AlterField(
            model_name='participantlockmodel',
            name='participant_code',
            field=otree.db.models.CharField(max_length=16, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='session',
            name='code',
            field=otree.db.models.CharField(max_length=16, null=True, default=otree.common_internal.random_chars_8, unique=True),
        ),
    ]
