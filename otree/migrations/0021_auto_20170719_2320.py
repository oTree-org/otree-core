# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0020_auto_20170507_0042'),
    ]

    operations = [
        migrations.RenameField(
            model_name='session',
            old_name='mturk_sandbox',
            new_name='mturk_use_sandbox',
        ),
    ]
