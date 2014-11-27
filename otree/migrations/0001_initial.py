# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import save_the_change.mixins
import otree.db.models
import otree.fields


class Migration(migrations.Migration):

    dependencies = [
        ('session', '0001_initial'),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompletedGroupWaitPage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('app_name', otree.db.models.CharField(max_length=300, null=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('group_pk', otree.db.models.PositiveIntegerField(null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CompletedSubsessionWaitPage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('app_name', otree.db.models.CharField(max_length=300, null=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('subsession_pk', otree.db.models.PositiveIntegerField(null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Experimenter',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', otree.db.models.RandomCharField(max_length=8, null=True, blank=True)),
                ('visited', otree.db.models.BooleanField(default=False)),
                ('index_in_pages', otree.db.models.PositiveIntegerField(default=0, null=True)),
                ('_me_in_previous_subsession_object_id', otree.db.models.PositiveIntegerField(null=True)),
                ('_me_in_next_subsession_object_id', otree.db.models.PositiveIntegerField(null=True)),
                ('subsession_object_id', otree.db.models.PositiveIntegerField(null=True)),
                ('_me_in_next_subsession_content_type', models.ForeignKey(related_name='otree_experimenter_next', to='contenttypes.ContentType', null=True)),
                ('_me_in_previous_subsession_content_type', models.ForeignKey(related_name='otree_experimenter_previous', to='contenttypes.ContentType', null=True)),
                ('session', models.ForeignKey(related_name='otree_experimenter', to='session.Session')),
                ('session_experimenter', models.ForeignKey(related_name='experimenter', to='session.SessionExperimenter', null=True)),
                ('subsession_content_type', models.ForeignKey(related_name='experimenter', to='contenttypes.ContentType', null=True)),
            ],
            options={
            },
            bases=(save_the_change.mixins.SaveTheChange, models.Model),
        ),
        migrations.CreateModel(
            name='PageExpirationTime',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('app_name', otree.db.models.CharField(max_length=300, null=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('player_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('expiration_time', otree.db.models.PositiveIntegerField(null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PageVisit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('app_name', otree.db.models.CharField(max_length=300, null=True)),
                ('player_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('page_name', otree.db.models.CharField(max_length=300, null=True)),
                ('completion_time_stamp', otree.db.models.DateTimeField(null=True)),
                ('seconds_on_page', otree.db.models.PositiveIntegerField(null=True)),
                ('subsession_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('participant_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('session_pk', otree.db.models.PositiveIntegerField(null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='WaitPageVisit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('app_name', otree.db.models.CharField(max_length=300, null=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('player_pk', otree.db.models.PositiveIntegerField(null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
