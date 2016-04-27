# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import otree.db.models


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='participant',
            name='_current_app_name',
            field=otree.db.models.CharField(null=True, verbose_name='app', max_length=200),
        ),
        migrations.AlterField(
            model_name='participant',
            name='_current_page_name',
            field=otree.db.models.CharField(null=True, verbose_name='page', max_length=200),
        ),
        migrations.AlterField(
            model_name='participant',
            name='last_request_succeeded',
            field=otree.db.models.BooleanField(verbose_name='Health of last server request', choices=[(True, 'Yes'), (False, 'No')]),
        ),
        migrations.AlterField(
            model_name='session',
            name='experimenter_name',
            field=otree.db.models.CharField(null=True, max_length=300, blank=True, help_text='For internal record-keeping'),
        ),
        migrations.AlterField(
            model_name='session',
            name='label',
            field=otree.db.models.CharField(null=True, max_length=300, blank=True, help_text='For internal record-keeping'),
        ),
        migrations.AlterField(
            model_name='session',
            name='mturk_HITGroupId',
            field=otree.db.models.CharField(null=True, max_length=300, blank=True, help_text='Hit id for this session on MTurk'),
        ),
        migrations.AlterField(
            model_name='session',
            name='mturk_HITId',
            field=otree.db.models.CharField(null=True, max_length=300, blank=True, help_text='Hit id for this session on MTurk'),
        ),
        migrations.AlterField(
            model_name='session',
            name='mturk_num_participants',
            field=otree.db.models.IntegerField(null=True, help_text='Number of participants on MTurk', default=-1),
        ),
        migrations.AlterField(
            model_name='session',
            name='mturk_qualification_type_id',
            field=otree.db.models.CharField(null=True, max_length=300, blank=True, help_text='Qualification type that is assigned to each worker taking hit'),
        ),
        migrations.AlterField(
            model_name='session',
            name='mturk_sandbox',
            field=otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], help_text='Should this session be created in mturk sandbox?', default=True),
        ),
        migrations.AlterField(
            model_name='session',
            name='time_scheduled',
            field=otree.db.models.DateTimeField(null=True, blank=True, help_text='For internal record-keeping'),
        ),
    ]
