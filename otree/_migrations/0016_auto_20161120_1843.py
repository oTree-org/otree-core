# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import otree.db.models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0015_auto_20161111_1055'),
    ]

    operations = [
        migrations.AddField(
            model_name='completedgroupwaitpage',
            name='id_in_subsession',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='session',
            name='_admin_report_app_names',
            field=otree.db.models.TextField(default='', null=True),
        ),
        migrations.AddField(
            model_name='session',
            name='_admin_report_num_rounds',
            field=otree.db.models.CharField(default='', max_length=255, null=True),
        ),
        migrations.AlterUniqueTogether(
            name='completedgroupwaitpage',
            unique_together=set([('page_index', 'session', 'id_in_subsession')]),
        ),
        migrations.AlterIndexTogether(
            name='completedgroupwaitpage',
            index_together=set([('page_index', 'session', 'id_in_subsession')]),
        ),
        migrations.RemoveField(
            model_name='completedgroupwaitpage',
            name='group_pk',
        ),
    ]
