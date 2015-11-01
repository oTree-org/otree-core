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


class WaitPageVisit(models.Model):
    '''difference between this and PageVisit model is that this is run
    when the player first loads the page, rather than when they leave

    '''
    class Meta:
        app_label = "otree"

    session_pk = models.PositiveIntegerField(db_index=True)
    page_index = models.PositiveIntegerField(db_index=True)

    id_in_session = models.PositiveIntegerField(db_index=True)


class PageTimeout(models.Model):
    class Meta:
        app_label = "otree"

    participant_pk = models.PositiveIntegerField()
    page_index = models.PositiveIntegerField()
    expiration_time = models.PositiveIntegerField()


class CompletedGroupWaitPage(models.Model):
    class Meta:
        app_label = "otree"
        index_together = ['page_index', 'session_pk', 'group_pk']

    page_index = models.PositiveIntegerField(db_index=True)
    session_pk = models.PositiveIntegerField(db_index=True)
    group_pk = models.PositiveIntegerField(db_index=True)


class CompletedSubsessionWaitPage(models.Model):
    class Meta:
        app_label = "otree"
        index_together = ['page_index', 'session_pk']

    page_index = models.PositiveIntegerField(db_index=True)
    session_pk = models.PositiveIntegerField(db_index=True)


class ParticipantToPlayerLookup(models.Model):
    class Meta:
        app_label = "otree"

    participant_pk = models.PositiveIntegerField()
    page_index = models.PositiveIntegerField()
    app_name = models.CharField(max_length=300)
    player_pk = models.PositiveIntegerField()


class GroupSize(models.Model):
    class Meta:
        app_label = "otree"

    app_label = models.CharField(max_length=300, db_index=True)
    subsession_pk = models.PositiveIntegerField(db_index=True)
    group_index = models.PositiveIntegerField()
    group_size = models.PositiveIntegerField()


class ParticipantLockModel(models.Model):
    class Meta:
        app_label = "otree"

    participant_code = models.CharField(max_length=10)


class StubModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be
    omitted. Consider using SingletonModel for this. Right now, I'm not
    sure we need it.

    """

    class Meta:
        app_label = "otree"

    pass
