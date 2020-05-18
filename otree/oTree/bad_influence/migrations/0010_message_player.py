# Generated by Django 2.2.4 on 2020-04-20 13:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bad_influence', '0009_remove_message_player'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='player',
            field=models.OneToOneField(default=1, on_delete=django.db.models.deletion.CASCADE, to='bad_influence.Player'),
            preserve_default=False,
        ),
    ]