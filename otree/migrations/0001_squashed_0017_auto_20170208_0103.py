# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import otree.models.varsmixin
import otree.db.models
import otree.common_internal


class Migration(migrations.Migration):

    replaces = [('otree', '0001_initial'), ('otree', '0002_browserbotsubmit_is_last'), ('otree', '0003_participant__browser_bot_finished'), ('otree', '0004_auto_20160704_1636'), ('otree', '0005_auto_20160707_1914'), ('otree', '0006_auto_20160708_0657'), ('otree', '0007_auto_20160726_1956'), ('otree', '0008_auto_20160728_1916'), ('otree', '0009_browserbotslaunchersessioncode'), ('otree', '0010_session__bot_case_number'), ('otree', '0011_auto_20160805_1735'), ('otree', '0012_auto_20160821_2339'), ('otree', '0013_failedsessioncreation_traceback'), ('otree', '0014_auto_20161012_0539'), ('otree', '0015_auto_20161111_1055'), ('otree', '0016_auto_20161120_1843'), ('otree', '0017_auto_20170208_0103')]

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CompletedGroupWaitPage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('page_index', models.PositiveIntegerField()),
                ('group_pk', models.PositiveIntegerField()),
                ('after_all_players_arrive_run', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='CompletedSubsessionWaitPage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('page_index', models.PositiveIntegerField()),
                ('after_all_players_arrive_run', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='ExpectedRoomParticipant',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('room_name', models.CharField(max_length=50)),
                ('participant_label', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='FailedSessionCreation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('pre_create_id', models.CharField(max_length=100, db_index=True)),
                ('message', models.CharField(max_length=300)),
                ('traceback', models.TextField(default='')),
            ],
        ),
        migrations.CreateModel(
            name='PageCompletion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('app_name', models.CharField(max_length=300)),
                ('page_index', models.PositiveIntegerField()),
                ('page_name', models.CharField(max_length=300)),
                ('time_stamp', models.PositiveIntegerField()),
                ('seconds_on_page', models.PositiveIntegerField()),
                ('subsession_pk', models.PositiveIntegerField()),
                ('auto_submitted', models.BooleanField()),
            ],
        ),
        migrations.CreateModel(
            name='PageTimeout',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('page_index', models.PositiveIntegerField()),
                ('expiration_time', models.PositiveIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Participant',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('vars', otree.db.models._JSONField(null=True, default=dict)),
                ('exclude_from_data_analysis', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('time_started', otree.db.models.DateTimeField(null=True)),
                ('mturk_assignment_id', otree.db.models.CharField(max_length=50, null=True)),
                ('mturk_worker_id', otree.db.models.CharField(max_length=50, null=True)),
                ('start_order', otree.db.models.PositiveIntegerField(null=True, db_index=True)),
                ('label', otree.db.models.CharField(max_length=50, null=True)),
                ('_index_in_subsessions', otree.db.models.PositiveIntegerField(null=True, default=0)),
                ('_index_in_pages', otree.db.models.PositiveIntegerField(null=True, db_index=True, default=0)),
                ('id_in_session', otree.db.models.PositiveIntegerField(null=True)),
                ('_waiting_for_ids', otree.db.models.CharField(max_length=300, null=True)),
                ('code', otree.db.models.CharField(max_length=16, unique=True, null=True, default=otree.common_internal.random_chars_8)),
                ('last_request_succeeded', otree.db.models.BooleanField(verbose_name='Health of last server request', choices=[(True, 'Yes'), (False, 'No')])),
                ('visited', otree.db.models.BooleanField(db_index=True, default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('ip_address', otree.db.models.GenericIPAddressField(null=True)),
                ('_last_page_timestamp', otree.db.models.PositiveIntegerField(null=True)),
                ('_last_request_timestamp', otree.db.models.PositiveIntegerField(null=True)),
                ('is_on_wait_page', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('_current_page_name', otree.db.models.CharField(verbose_name='page', max_length=200, null=True)),
                ('_current_app_name', otree.db.models.CharField(verbose_name='app', max_length=200, null=True)),
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
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('participant_code', models.CharField(max_length=16, unique=True)),
                ('locked', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='ParticipantRoomVisit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('room_name', models.CharField(max_length=50)),
                ('participant_label', models.CharField(max_length=200)),
                ('tab_unique_id', models.CharField(max_length=20, unique=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='ParticipantToPlayerLookup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('page_index', models.PositiveIntegerField()),
                ('app_name', models.CharField(max_length=300)),
                ('player_pk', models.PositiveIntegerField()),
                ('url', models.CharField(max_length=300)),
                ('participant', models.ForeignKey(to='otree.Participant')),
            ],
        ),
        migrations.CreateModel(
            name='RoomToSession',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('room_name', models.CharField(max_length=255, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Session',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('vars', otree.db.models._JSONField(null=True, default=dict)),
                ('config', otree.db.models._JSONField(null=True, default=dict)),
                ('label', otree.db.models.CharField(max_length=300, blank=True, null=True, help_text='For internal record-keeping')),
                ('experimenter_name', otree.db.models.CharField(max_length=300, blank=True, null=True, help_text='For internal record-keeping')),
                ('code', otree.db.models.CharField(max_length=16, unique=True, null=True, default=otree.common_internal.random_chars_8)),
                ('time_scheduled', otree.db.models.DateTimeField(blank=True, null=True, help_text='For internal record-keeping')),
                ('time_started', otree.db.models.DateTimeField(null=True)),
                ('mturk_HITId', otree.db.models.CharField(max_length=300, blank=True, null=True, help_text='Hit id for this session on MTurk')),
                ('mturk_HITGroupId', otree.db.models.CharField(max_length=300, blank=True, null=True, help_text='Hit id for this session on MTurk')),
                ('mturk_qualification_type_id', otree.db.models.CharField(max_length=300, blank=True, null=True, help_text='Qualification type that is assigned to each worker taking hit')),
                ('mturk_num_participants', otree.db.models.IntegerField(null=True, default=-1, help_text='Number of participants on MTurk')),
                ('mturk_sandbox', otree.db.models.BooleanField(default=True, choices=[(True, 'Yes'), (False, 'No')], help_text='Should this session be created in mturk sandbox?')),
                ('archived', otree.db.models.BooleanField(db_index=True, default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('comment', otree.db.models.TextField(blank=True, null=True)),
                ('_anonymous_code', otree.db.models.CharField(max_length=10, null=True, db_index=True, default=otree.common_internal.random_chars_10)),
                ('_pre_create_id', otree.db.models.CharField(max_length=300, null=True, db_index=True)),
                ('_use_browser_bots', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('_bots_errored', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('_bots_finished', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('_cannot_restart_bots', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('has_bots', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('is_demo', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
                ('ready', otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')])),
            ],
            options={
                'ordering': ['pk'],
            },
            bases=(otree.models.varsmixin._SaveTheChangeWithCustomFieldSupport, models.Model),
        ),
        migrations.CreateModel(
            name='UndefinedFormModel',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
            ],
        ),
        migrations.AddField(
            model_name='roomtosession',
            name='session',
            field=models.ForeignKey(to='otree.Session'),
        ),
        migrations.AddField(
            model_name='participant',
            name='session',
            field=models.ForeignKey(to='otree.Session'),
        ),
        migrations.AddField(
            model_name='pagetimeout',
            name='participant',
            field=models.ForeignKey(to='otree.Participant'),
        ),
        migrations.AddField(
            model_name='pagecompletion',
            name='participant',
            field=models.ForeignKey(to='otree.Participant'),
        ),
        migrations.AddField(
            model_name='pagecompletion',
            name='session',
            field=models.ForeignKey(to='otree.Session'),
        ),
        migrations.AlterUniqueTogether(
            name='expectedroomparticipant',
            unique_together=set([('room_name', 'participant_label')]),
        ),
        migrations.AddField(
            model_name='completedsubsessionwaitpage',
            name='session',
            field=models.ForeignKey(to='otree.Session'),
        ),
        migrations.AddField(
            model_name='completedgroupwaitpage',
            name='session',
            field=models.ForeignKey(to='otree.Session'),
        ),
        migrations.AlterUniqueTogether(
            name='participanttoplayerlookup',
            unique_together=set([('participant', 'page_index')]),
        ),
        migrations.AlterIndexTogether(
            name='participanttoplayerlookup',
            index_together=set([('participant', 'page_index')]),
        ),
        migrations.AlterIndexTogether(
            name='participant',
            index_together=set([('session', 'mturk_worker_id', 'mturk_assignment_id')]),
        ),
        migrations.AlterIndexTogether(
            name='pagetimeout',
            index_together=set([('participant', 'page_index')]),
        ),
        migrations.AlterUniqueTogether(
            name='completedsubsessionwaitpage',
            unique_together=set([('page_index', 'session')]),
        ),
        migrations.AlterIndexTogether(
            name='completedsubsessionwaitpage',
            index_together=set([('page_index', 'session')]),
        ),
        migrations.AlterUniqueTogether(
            name='completedgroupwaitpage',
            unique_together=set([('page_index', 'session', 'group_pk')]),
        ),
        migrations.AlterIndexTogether(
            name='completedgroupwaitpage',
            index_together=set([('page_index', 'session', 'group_pk')]),
        ),
        migrations.AddField(
            model_name='participant',
            name='_browser_bot_finished',
            field=otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')]),
        ),
        migrations.CreateModel(
            name='GlobalLockModel',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('locked', models.BooleanField(default=False)),
            ],
        ),
        migrations.RemoveField(
            model_name='participant',
            name='_is_auto_playing',
        ),
        migrations.AddField(
            model_name='participant',
            name='_is_bot',
            field=otree.db.models.BooleanField(default=False, choices=[(True, 'Yes'), (False, 'No')]),
        ),
        migrations.AlterModelOptions(
            name='participant',
            options={},
        ),
        migrations.AlterModelOptions(
            name='session',
            options={},
        ),
        migrations.AlterIndexTogether(
            name='participant',
            index_together=set([]),
        ),
        migrations.CreateModel(
            name='BrowserBotsLauncherSessionCode',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('code', models.CharField(max_length=10)),
                ('is_only_record', models.BooleanField(unique=True, default=True)),
            ],
        ),
        migrations.AddField(
            model_name='session',
            name='_bot_case_number',
            field=otree.db.models.PositiveIntegerField(null=True),
        ),
        migrations.RenameField(
            model_name='session',
            old_name='_use_browser_bots',
            new_name='use_browser_bots',
        ),
        migrations.AlterModelOptions(
            name='participant',
            options={'ordering': ['pk']},
        ),
        migrations.AlterModelOptions(
            name='session',
            options={'ordering': ['pk']},
        ),
        migrations.AlterIndexTogether(
            name='participant',
            index_together=set([('session', 'mturk_worker_id', 'mturk_assignment_id')]),
        ),
        migrations.RenameField(
            model_name='completedgroupwaitpage',
            old_name='after_all_players_arrive_run',
            new_name='fully_completed',
        ),
        migrations.RenameField(
            model_name='completedsubsessionwaitpage',
            old_name='after_all_players_arrive_run',
            new_name='fully_completed',
        ),
        migrations.AlterField(
            model_name='session',
            name='_pre_create_id',
            field=otree.db.models.CharField(max_length=255, null=True, db_index=True),
        ),
        migrations.AddField(
            model_name='completedgroupwaitpage',
            name='id_in_subsession',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='session',
            name='_admin_report_app_names',
            field=otree.db.models.TextField(null=True, default=''),
        ),
        migrations.AddField(
            model_name='session',
            name='_admin_report_num_rounds',
            field=otree.db.models.CharField(max_length=255, null=True, default=''),
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
        migrations.RemoveField(
            model_name='session',
            name='time_scheduled',
        ),
        migrations.RemoveField(
            model_name='session',
            name='time_started',
        ),
    ]
