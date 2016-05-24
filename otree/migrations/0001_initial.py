# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import otree.db.models
import otree.common_internal
import otree.models.varsmixin


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CompletedGroupWaitPage',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('session_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('group_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('after_all_players_arrive_run', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False)),
            ],
        ),
        migrations.CreateModel(
            name='CompletedSubsessionWaitPage',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('session_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('after_all_players_arrive_run', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False)),
            ],
        ),
        migrations.CreateModel(
            name='FailedSessionCreation',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('pre_create_id', otree.db.models.CharField(max_length=100, null=True, db_index=True)),
            ],
            options={
                'db_table': 'otree_failedsessioncreation',
            },
        ),
        migrations.CreateModel(
            name='GlobalSingleton',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('locked', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False)),
            ],
        ),
        migrations.CreateModel(
            name='PageCompletion',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('app_name', otree.db.models.CharField(max_length=300, null=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('page_name', otree.db.models.CharField(max_length=300, null=True)),
                ('time_stamp', otree.db.models.PositiveIntegerField(null=True)),
                ('seconds_on_page', otree.db.models.PositiveIntegerField(null=True)),
                ('subsession_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('participant_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('session_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('auto_submitted', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')])),
            ],
        ),
        migrations.CreateModel(
            name='PageTimeout',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('participant_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('expiration_time', otree.db.models.PositiveIntegerField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Participant',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('vars', otree.db.models.JSONField(null=True, default=dict)),
                ('exclude_from_data_analysis', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False)),
                ('time_started', otree.db.models.DateTimeField(null=True)),
                ('mturk_assignment_id', otree.db.models.CharField(max_length=50, null=True)),
                ('mturk_worker_id', otree.db.models.CharField(max_length=50, null=True)),
                ('start_order', otree.db.models.PositiveIntegerField(null=True, db_index=True)),
                ('label', otree.db.models.CharField(max_length=50, null=True)),
                ('_index_in_subsessions', otree.db.models.PositiveIntegerField(null=True, default=0)),
                ('_index_in_pages', otree.db.models.PositiveIntegerField(null=True, db_index=True, default=0)),
                ('id_in_session', otree.db.models.PositiveIntegerField(null=True)),
                ('_waiting_for_ids', otree.db.models.CharField(max_length=300, null=True)),
                ('code', otree.db.models.CharField(max_length=16, null=True, unique=True, db_index=True, default=otree.common_internal.random_chars_8)),
                ('last_request_succeeded', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], verbose_name='Health of last server request')),
                ('visited', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], db_index=True, default=False)),
                ('ip_address', otree.db.models.GenericIPAddressField(null=True)),
                ('_last_page_timestamp', otree.db.models.PositiveIntegerField(null=True)),
                ('_last_request_timestamp', otree.db.models.PositiveIntegerField(null=True)),
                ('is_on_wait_page', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False)),
                ('_current_page_name', otree.db.models.CharField(max_length=200, null=True, verbose_name='page')),
                ('_current_app_name', otree.db.models.CharField(max_length=200, null=True, verbose_name='app')),
                ('_round_number', otree.db.models.PositiveIntegerField(null=True)),
                ('_current_form_page_url', otree.db.models.URLField(null=True)),
                ('_max_page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('_is_auto_playing', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False)),
            ],
            options={
                'ordering': ['pk'],
            },
            bases=(otree.models.varsmixin._SaveTheChangeWithCustomFieldSupport, models.Model),
        ),
        migrations.CreateModel(
            name='ParticipantLockModel',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('participant_code', otree.db.models.CharField(max_length=16, null=True, unique=True, db_index=True)),
                ('locked', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False)),
            ],
        ),
        migrations.CreateModel(
            name='ParticipantToPlayerLookup',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('participant_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('app_name', otree.db.models.CharField(max_length=300, null=True)),
                ('player_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('url', otree.db.models.CharField(max_length=300, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='RoomSession',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('room_name', otree.db.models.CharField(max_length=500, null=True, unique=True)),
                ('session_pk', otree.db.models.PositiveIntegerField(null=True)),
            ],
            options={
                'db_table': 'otree_roomsession',
            },
        ),
        migrations.CreateModel(
            name='Session',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('vars', otree.db.models.JSONField(null=True, default=dict)),
                ('config', otree.db.models.JSONField(null=True, default=dict)),
                ('label', otree.db.models.CharField(blank=True, max_length=300, help_text='For internal record-keeping', null=True)),
                ('experimenter_name', otree.db.models.CharField(blank=True, max_length=300, help_text='For internal record-keeping', null=True)),
                ('code', otree.db.models.CharField(max_length=16, null=True, unique=True, db_index=True, default=otree.common_internal.random_chars_8)),
                ('time_scheduled', otree.db.models.DateTimeField(blank=True, help_text='For internal record-keeping', null=True)),
                ('time_started', otree.db.models.DateTimeField(null=True)),
                ('mturk_HITId', otree.db.models.CharField(blank=True, max_length=300, help_text='Hit id for this session on MTurk', null=True)),
                ('mturk_HITGroupId', otree.db.models.CharField(blank=True, max_length=300, help_text='Hit id for this session on MTurk', null=True)),
                ('mturk_qualification_type_id', otree.db.models.CharField(blank=True, max_length=300, help_text='Qualification type that is assigned to each worker taking hit', null=True)),
                ('mturk_num_participants', otree.db.models.IntegerField(help_text='Number of participants on MTurk', null=True, default=-1)),
                ('mturk_sandbox', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], help_text='Should this session be created in mturk sandbox?', default=True)),
                ('archived', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], db_index=True, default=False)),
                ('git_commit_timestamp', otree.db.models.CharField(max_length=200, null=True)),
                ('comment', otree.db.models.TextField(blank=True, null=True)),
                ('_anonymous_code', otree.db.models.CharField(max_length=8, null=True, db_index=True, default=otree.common_internal.random_chars_10)),
                ('special_category', otree.db.models.CharField(max_length=20, null=True, db_index=True)),
                ('_pre_create_id', otree.db.models.CharField(max_length=300, null=True, db_index=True)),
            ],
            options={
                'ordering': ['pk'],
            },
            bases=(otree.models.varsmixin._SaveTheChangeWithCustomFieldSupport, models.Model),
        ),
        migrations.CreateModel(
            name='StubModel',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
            ],
        ),
        migrations.AlterIndexTogether(
            name='participanttoplayerlookup',
            index_together=set([('participant_pk', 'page_index')]),
        ),
        migrations.AddField(
            model_name='participant',
            name='session',
            field=otree.db.models.ForeignKey(to='otree.Session'),
        ),
        migrations.AlterIndexTogether(
            name='pagetimeout',
            index_together=set([('participant_pk', 'page_index')]),
        ),
        migrations.AlterUniqueTogether(
            name='completedsubsessionwaitpage',
            unique_together=set([('page_index', 'session_pk')]),
        ),
        migrations.AlterIndexTogether(
            name='completedsubsessionwaitpage',
            index_together=set([('page_index', 'session_pk')]),
        ),
        migrations.AlterUniqueTogether(
            name='completedgroupwaitpage',
            unique_together=set([('page_index', 'session_pk', 'group_pk')]),
        ),
        migrations.AlterIndexTogether(
            name='completedgroupwaitpage',
            index_together=set([('page_index', 'session_pk', 'group_pk')]),
        ),
        migrations.AlterIndexTogether(
            name='participant',
            index_together=set([('session', 'mturk_worker_id', 'mturk_assignment_id')]),
        ),
    ]
