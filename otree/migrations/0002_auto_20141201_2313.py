# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('otree', '0001_initial'),
        ('session', '0001_initial'),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='experimenter',
            name='session',
            field=models.ForeignKey(related_name='otree_experimenter', to='session.Session'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='experimenter',
            name='session_experimenter',
            field=models.ForeignKey(related_name='experimenter', to='session.SessionExperimenter', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='experimenter',
            name='subsession_content_type',
            field=models.ForeignKey(related_name='experimenter', to='contenttypes.ContentType', null=True),
            preserve_default=True,
        ),
    ]
