# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0019_delete_expectedroomparticipant'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pagetimeout',
            name='expiration_time',
            field=models.FloatField(),
        ),
    ]
