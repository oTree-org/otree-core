import time
from collections import defaultdict
from typing import Iterable

from django.db import models
import json


class PageTimeBatch(models.Model):
    text = models.TextField()


class CompletedGroupWaitPage(models.Model):
    '''
    separate model from GBAT because here we can use group_id which allows more efficient lookup.
    '''

    class Meta:
        app_label = "otree"
        index_together = ['page_index', 'session', 'group_id']

    page_index = models.PositiveIntegerField()
    session = models.ForeignKey('otree.Session', on_delete=models.CASCADE)
    group_id = models.PositiveIntegerField()


class CompletedGBATWaitPage(models.Model):
    class Meta:
        app_label = "otree"
        index_together = ['page_index', 'session', 'id_in_subsession']

    page_index = models.PositiveIntegerField()
    session = models.ForeignKey('otree.Session', on_delete=models.CASCADE)
    id_in_subsession = models.PositiveIntegerField(default=0)


class CompletedSubsessionWaitPage(models.Model):
    class Meta:
        app_label = "otree"
        index_together = ['page_index', 'session']

    page_index = models.PositiveIntegerField()
    session = models.ForeignKey('otree.Session', on_delete=models.CASCADE)


class ParticipantVarsFromREST(models.Model):
    class Meta:
        app_label = "otree"
        index_together = ['participant_label', 'room_name']
        unique_together = ['participant_label', 'room_name']

    participant_label = models.CharField(max_length=255)
    room_name = models.CharField(max_length=255)
    _json_data = models.TextField(default='')

    @property
    def vars(self):
        return json.loads(self._json_data)

    @vars.setter
    def vars(self, value):
        self._json_data = json.dumps(value)


class UndefinedFormModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be
    omitted. Consider using SingletonModel for this. Right now, I'm not
    sure we need it.

    """

    class Meta:
        app_label = "otree"

    pass


class RoomToSession(models.Model):
    class Meta:
        app_label = "otree"

    room_name = models.CharField(unique=True, max_length=255)
    session = models.ForeignKey('otree.Session', on_delete=models.CASCADE)


class ParticipantRoomVisit(models.Model):
    class Meta:
        app_label = "otree"

    room_name = models.CharField(max_length=50)
    participant_label = models.CharField(max_length=200)
    tab_unique_id = models.CharField(max_length=20, unique=True)
    last_updated = models.FloatField()


class BrowserBotsLauncherSessionCode(models.Model):
    class Meta:
        app_label = "otree"

    code = models.CharField(max_length=10)
    pre_create_id = models.CharField(max_length=10)

    # hack to enforce singleton
    is_only_record = models.BooleanField(unique=True, default=True)


class ChatMessage(models.Model):
    class Meta:
        index_together = ['channel', 'timestamp']

    # the name "channel" here is unrelated to Django channels
    channel = models.CharField(max_length=255)
    # related_name necessary to disambiguate with otreechat add on
    participant = models.ForeignKey(
        'otree.Participant', related_name='chat_messages_core', on_delete=models.CASCADE
    )
    nickname = models.CharField(max_length=255)

    # call it 'body' instead of 'message' or 'content' because those terms
    # are already used by channels
    body = models.TextField()
    timestamp = models.FloatField(default=time.time)
