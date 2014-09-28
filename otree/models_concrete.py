from otree.db import models

class WaitPageVisit(models.Model):

    app_name = models.CharField(max_length=300)
    wait_page_index = models.PositiveIntegerField()
    player_pk = models.PositiveIntegerField()

class CompletedMatchWaitPage(models.Model):
    app_name = models.CharField(max_length=300)
    wait_page_index = models.PositiveIntegerField()
    match_pk = models.PositiveIntegerField()

class CompletedSubsessionWaitPage(models.Model):
    app_name = models.CharField(max_length=300)
    wait_page_index = models.PositiveIntegerField()
    match_pk = models.PositiveIntegerField()
