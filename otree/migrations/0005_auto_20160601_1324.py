# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0004_participantroomvisit'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='RoomSession',
            new_name='RoomToSession',
        ),
        migrations.AlterModelTable(
            name='roomtosession',
            table='otree_roomtosession',
        ),
    ]
