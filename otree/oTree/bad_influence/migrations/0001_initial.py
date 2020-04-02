# Generated by Django 2.2.4 on 2020-04-02 08:58

from django.db import migrations, models
import django.db.models.deletion
import otree.db.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('otree', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_in_subsession', otree.db.models.PositiveIntegerField(db_index=True, null=True)),
                ('round_number', otree.db.models.PositiveIntegerField(db_index=True, null=True)),
                ('history', otree.db.models.LongStringField(default='[]', null=True)),
                ('graph', otree.db.models.LongStringField(null=True)),
                ('consensus', otree.db.models.FloatField(null=True)),
                ('question', otree.db.models.StringField(max_length=10000, null=True)),
                ('round_start_time', otree.db.models.FloatField(null=True)),
                ('round_end_time', otree.db.models.FloatField(null=True)),
                ('choice', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], null=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bad_influence_group', to='otree.Session')),
            ],
            options={
                'db_table': 'bad_influence_group',
            },
        ),
        migrations.CreateModel(
            name='Subsession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('round_number', otree.db.models.PositiveIntegerField(db_index=True, null=True)),
                ('full_network', otree.db.models.LongStringField(null=True)),
                ('consensus', otree.db.models.FloatField(null=True)),
                ('session', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bad_influence_subsession', to='otree.Session')),
            ],
            options={
                'db_table': 'bad_influence_subsession',
            },
        ),
        migrations.CreateModel(
            name='Player',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_in_group', otree.db.models.PositiveIntegerField(db_index=True, null=True)),
                ('_payoff', otree.db.models.CurrencyField(default=0, null=True)),
                ('round_number', otree.db.models.PositiveIntegerField(db_index=True, null=True)),
                ('_gbat_arrived', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, null=True)),
                ('_gbat_grouped', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], default=False, null=True)),
                ('ego_network', otree.db.models.LongStringField(null=True)),
                ('friends', otree.db.models.LongStringField(null=True)),
                ('hub', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], null=True)),
                ('choice', otree.db.models.BooleanField(choices=[[True, 'Rød'], [False, 'Blå']], null=True)),
                ('gender', otree.db.models.BooleanField(choices=[(True, 'Yes'), (False, 'No')], null=True)),
                ('number_of_friends', otree.db.models.IntegerField(null=True)),
                ('spg', otree.db.models.LongStringField(null=True)),
                ('last_choice_made_at', otree.db.models.IntegerField(null=True)),
                ('stubborn', otree.db.models.FloatField(default=0, null=True)),
                ('opinion_change', otree.db.models.IntegerField(default=0, null=True)),
                ('stubborn_total', otree.db.models.FloatField(default=0, null=True)),
                ('opinion_change_total', otree.db.models.IntegerField(default=0, null=True)),
                ('number_of_friends_total', otree.db.models.IntegerField(default=0, null=True)),
                ('group', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='bad_influence.Group')),
                ('participant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bad_influence_player', to='otree.Participant')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bad_influence_player', to='otree.Session')),
                ('subsession', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bad_influence.Subsession')),
            ],
            options={
                'db_table': 'bad_influence_player',
            },
        ),
        migrations.AddField(
            model_name='group',
            name='subsession',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bad_influence.Subsession'),
        ),
    ]
