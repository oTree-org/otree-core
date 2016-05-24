# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import otree.db.models
import otree.models.varsmixin
import otree.common_internal


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CompletedGroupWaitPage',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('session_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('group_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('after_all_players_arrive_run', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
            ],
        ),
        migrations.CreateModel(
            name='CompletedSubsessionWaitPage',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('session_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('after_all_players_arrive_run', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
            ],
        ),
        migrations.CreateModel(
            name='FailedSessionCreation',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('pre_create_id', otree.db.models.CharField(null=True, db_index=True, max_length=100)),
            ],
            options={
                'db_table': 'otree_failedsessioncreation',
            },
        ),
        migrations.CreateModel(
            name='GlobalSingleton',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('locked', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
            ],
        ),
        migrations.CreateModel(
            name='PageCompletion',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('app_name', otree.db.models.CharField(null=True, max_length=300)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('page_name', otree.db.models.CharField(null=True, max_length=300)),
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
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('participant_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('expiration_time', otree.db.models.PositiveIntegerField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Participant',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('vars', otree.db.models.JSONField(default=dict, null=True)),
                ('exclude_from_data_analysis', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('time_started', otree.db.models.DateTimeField(null=True)),
                ('mturk_assignment_id', otree.db.models.CharField(null=True, max_length=50)),
                ('mturk_worker_id', otree.db.models.CharField(null=True, max_length=50)),
                ('start_order', otree.db.models.PositiveIntegerField(db_index=True, null=True)),
                ('label', otree.db.models.CharField(null=True, max_length=50)),
                ('_index_in_subsessions', otree.db.models.PositiveIntegerField(default=0, null=True)),
                ('_index_in_pages', otree.db.models.PositiveIntegerField(default=0, db_index=True, null=True)),
                ('id_in_session', otree.db.models.PositiveIntegerField(null=True)),
                ('_waiting_for_ids', otree.db.models.CharField(null=True, max_length=300)),
                ('code', otree.db.models.CharField(default=otree.common_internal.random_chars_8, unique=True, db_index=True, max_length=16, null=True)),
                ('last_request_succeeded', otree.db.models.BooleanField(verbose_name='Health of last server request', choices=[(True, 'Yes'), (False, 'No')])),
                ('visited', otree.db.models.BooleanField(default=False, db_index=True, choices=[(True, 'Yes'), (False, 'No')])),
                ('ip_address', otree.db.models.GenericIPAddressField(null=True)),
                ('_last_page_timestamp', otree.db.models.PositiveIntegerField(null=True)),
                ('_last_request_timestamp', otree.db.models.PositiveIntegerField(null=True)),
                ('is_on_wait_page', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('_current_page_name', otree.db.models.CharField(null=True, verbose_name='page', max_length=200)),
                ('_current_app_name', otree.db.models.CharField(null=True, verbose_name='app', max_length=200)),
                ('_round_number', otree.db.models.PositiveIntegerField(null=True)),
                ('_current_form_page_url', otree.db.models.URLField(null=True)),
                ('_max_page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('_is_auto_playing', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
            ],
            options={
                'ordering': ['pk'],
            },
            bases=(otree.models.varsmixin._SaveTheChangeWithCustomFieldSupport, models.Model),
        ),
        migrations.CreateModel(
            name='ParticipantLockModel',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('participant_code', otree.db.models.CharField(unique=True, null=True, db_index=True, max_length=16)),
                ('locked', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
            ],
        ),
        migrations.CreateModel(
            name='ParticipantToPlayerLookup',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('participant_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('page_index', otree.db.models.PositiveIntegerField(null=True)),
                ('app_name', otree.db.models.CharField(null=True, max_length=300)),
                ('player_pk', otree.db.models.PositiveIntegerField(null=True)),
                ('url', otree.db.models.CharField(null=True, max_length=300)),
            ],
        ),
        migrations.CreateModel(
            name='RoomSession',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('room_name', otree.db.models.CharField(unique=True, null=True, max_length=500)),
                ('session_pk', otree.db.models.PositiveIntegerField(null=True)),
            ],
            options={
                'db_table': 'otree_roomsession',
            },
        ),
        migrations.CreateModel(
            name='Session',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
                ('vars', otree.db.models.JSONField(default=dict, null=True)),
                ('config', otree.db.models.JSONField(default=dict, null=True)),
                ('label', otree.db.models.CharField(null=True, max_length=300, help_text='For internal record-keeping', blank=True)),
                ('experimenter_name', otree.db.models.CharField(null=True, max_length=300, help_text='For internal record-keeping', blank=True)),
                ('code', otree.db.models.CharField(default=otree.common_internal.random_chars_8, unique=True, db_index=True, max_length=16, null=True)),
                ('time_scheduled', otree.db.models.DateTimeField(null=True, help_text='For internal record-keeping', blank=True)),
                ('time_started', otree.db.models.DateTimeField(null=True)),
                ('mturk_HITId', otree.db.models.CharField(null=True, max_length=300, help_text='Hit id for this session on MTurk', blank=True)),
                ('mturk_HITGroupId', otree.db.models.CharField(null=True, max_length=300, help_text='Hit id for this session on MTurk', blank=True)),
                ('mturk_qualification_type_id', otree.db.models.CharField(null=True, max_length=300, help_text='Qualification type that is assigned to each worker taking hit', blank=True)),
                ('mturk_num_participants', otree.db.models.IntegerField(default=-1, null=True, help_text='Number of participants on MTurk')),
                ('mturk_sandbox', otree.db.models.BooleanField(default=True, help_text='Should this session be created in mturk sandbox?', choices=[(True, 'Yes'), (False, 'No')])),
                ('archived', otree.db.models.BooleanField(default=False, db_index=True, choices=[(True, 'Yes'), (False, 'No')])),
                ('git_commit_timestamp', otree.db.models.CharField(null=True, max_length=200)),
                ('comment', otree.db.models.TextField(null=True, blank=True)),
                ('_ready_to_play', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('_anonymous_code', otree.db.models.CharField(default=otree.common_internal.random_chars_10, null=True, db_index=True, max_length=8)),
                ('special_category', otree.db.models.CharField(null=True, db_index=True, max_length=20)),
                ('demo_already_used', otree.db.models.BooleanField(default=False, db_index=True, choices=[(True, 'Yes'), (False, 'No')])),
                ('ready', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('_pre_create_id', otree.db.models.CharField(null=True, db_index=True, max_length=300)),
            ],
            options={
                'ordering': ['pk'],
            },
            bases=(otree.models.varsmixin._SaveTheChangeWithCustomFieldSupport, models.Model),
        ),
        migrations.CreateModel(
            name='StubModel',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', serialize=False, primary_key=True)),
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
