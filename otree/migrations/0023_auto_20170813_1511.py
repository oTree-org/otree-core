# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import otree.db.serializedfields
import otree.db.models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0022_remove_session_mturk_qualification_type_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='participant',
            name='last_request_succeeded',
        ),
        migrations.AddField(
            model_name='session',
            name='num_participants',
            field=otree.db.models.PositiveIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='participant',
            name='vars',
            field=otree.db.serializedfields._PickleField(default=dict),
        ),
        migrations.AlterField(
            model_name='session',
            name='config',
            field=otree.db.serializedfields._PickleField(null=True, default=dict),
        ),
        migrations.AlterField(
            model_name='session',
            name='vars',
            field=otree.db.serializedfields._PickleField(default=dict),
        ),
    ]
