from otree.db import models


class PageCompletion(models.Model):
    class Meta:
        app_label = "otree"

    app_name = models.CharField(max_length=300)
    page_index = models.PositiveIntegerField()
    page_name = models.CharField(max_length=300)
    time_stamp = models.PositiveIntegerField()
    seconds_on_page = models.PositiveIntegerField()
    subsession_pk = models.PositiveIntegerField()
    participant_pk = models.PositiveIntegerField()
    session_pk = models.PositiveIntegerField()
    auto_submitted = models.BooleanField()


class PageTimeout(models.Model):
    class Meta:
        app_label = "otree"
        index_together = ['participant_pk', 'page_index']

    participant_pk = models.PositiveIntegerField()
    page_index = models.PositiveIntegerField()
    expiration_time = models.PositiveIntegerField()


class CompletedGroupWaitPage(models.Model):
    class Meta:
        app_label = "otree"
        unique_together = ['page_index', 'session_pk', 'group_pk']
        index_together = ['page_index', 'session_pk', 'group_pk']


    page_index = models.PositiveIntegerField()
    session_pk = models.PositiveIntegerField()
    group_pk = models.PositiveIntegerField()
    after_all_players_arrive_run = models.BooleanField(default=False)

class CompletedSubsessionWaitPage(models.Model):
    class Meta:
        app_label = "otree"
        unique_together = ['page_index', 'session_pk']
        index_together = ['page_index', 'session_pk']


    page_index = models.PositiveIntegerField()
    session_pk = models.PositiveIntegerField()
    after_all_players_arrive_run = models.BooleanField(default=False)

class ParticipantToPlayerLookup(models.Model):
    class Meta:
        app_label = "otree"
        index_together = ['participant_pk', 'page_index']

    participant_pk = models.PositiveIntegerField()
    page_index = models.PositiveIntegerField()
    app_name = models.CharField(max_length=300)
    player_pk = models.PositiveIntegerField()
    url = models.CharField(max_length=300)


class ParticipantLockModel(models.Model):
    class Meta:
        app_label = "otree"

    participant_code = models.CharField(
        max_length=16, db_index=True, unique=True
    )

    locked = models.BooleanField(default=False)


class StubModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be
    omitted. Consider using SingletonModel for this. Right now, I'm not
    sure we need it.

    """

    class Meta:
        app_label = "otree"

    pass


class RoomSession(models.Model):
    room_name = models.CharField(unique=True)
    session_pk = models.PositiveIntegerField()


class FailedSessionCreation(models.Model):
    pre_create_id = models.CharField(max_length=100, db_index=True)


class ParticipantVisit(models.Model):
    room_name = models.CharField()
    participant_id = models.CharField(unique=True)
    duplicate_connection_count = models.PositiveIntegerField()
