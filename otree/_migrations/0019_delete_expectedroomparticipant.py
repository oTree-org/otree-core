# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0018_participant_payoff'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ExpectedRoomParticipant',
        ),
    ]
