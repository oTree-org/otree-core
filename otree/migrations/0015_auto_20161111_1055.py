# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import otree.db.models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0014_auto_20161012_0539'),
    ]

    operations = [
        migrations.AlterField(
            model_name='session',
            name='_pre_create_id',
            field=otree.db.models.CharField(null=True, db_index=True, max_length=255),
        ),
    ]
