# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import otree.db.models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0017_auto_20170208_0103'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='payoff',
            field=otree.db.models.CurrencyField(null=True, default=0, max_digits=12),
        ),
    ]
