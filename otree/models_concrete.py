from otree.db import models

class PageVisit(models.Model):
    app_name = models.CharField(max_length=300)
    player_pk = models.PositiveIntegerField()
    page_index = models.PositiveIntegerField()
    page_name = models.CharField(max_length=300)
    completion_time_stamp = models.DateTimeField()
    seconds_on_page = models.PositiveIntegerField()

    subsession_pk = models.PositiveIntegerField()
    participant_pk = models.PositiveIntegerField()
    session_pk = models.PositiveIntegerField()

class WaitPageVisit(models.Model):
    '''difference between this and PageVisit model is that this is run when the player first loads the page, rather than when they leave'''
    app_name = models.CharField(max_length=300)
    page_index = models.PositiveIntegerField()
    player_pk = models.PositiveIntegerField()

class CompletedGroupWaitPage(models.Model):
    app_name = models.CharField(max_length=300)
    page_index = models.PositiveIntegerField()
    group_pk = models.PositiveIntegerField()

class CompletedSubsessionWaitPage(models.Model):
    app_name = models.CharField(max_length=300)
    page_index = models.PositiveIntegerField()
    subsession_pk = models.PositiveIntegerField()

class PageExpirationTime(models.Model):
    '''is calculated on GET'''
    app_name = models.CharField(max_length=300)
    page_index = models.PositiveIntegerField()
    player_pk = models.PositiveIntegerField()
    expiration_time = models.PositiveIntegerField()