from otree.db import models
import time
from django.test import Client
from otree.common_internal import get_models_module

class UnsubmittedTimeoutPage(models.Model):
    '''is calculated on GET'''
    app_name = models.CharField(max_length=300)
    page_index = models.PositiveIntegerField()
    player_pk = models.PositiveIntegerField()
    expiration_time = models.PositiveIntegerField()

    # the URL to which an empty POST request should be submitted
    expiration_post_url = models.URLField()
    auto_submitted = models.BooleanField(default=False)

def submit_expired_urls():
    """
    After a page has been displayed for the given amount of time, we force it forward.
    This function should be called on a pre-set schedules.

    An alternative design would be for the expiration_post_url's to be put in a queue with a timestamp for when they should be executed.
    Like cron or celery.
    That's probably more efficient. But we only want to submit the pages that were not actually visited.
    """

    c = Client()

    GRACE_PERIOD_SECONDS = 15

    # but have to make sure this doesn't cause any circularity, where it looks like the page was never visited
    # in the first place.
    expired_pages = UnsubmittedTimeoutPage.objects.filter(
        expiration_time_gt = time.time() + GRACE_PERIOD_SECONDS,
    )
    for expired_page in expired_pages:
        c.post(expired_page.expiration_post_url, follow=True)

def ensure_pages_visited(app_name, player_pk_set, page_index):
    """
    This is necessary when a wait page is followed by a timeout page.
    We can't guarantee the user's browser will properly continue to poll the wait page and get redirected,
    so after a grace period we load the page automatically, to kick off the expiration timer of the timeout page."""

    # grace period because we want to give the user a chance to visit the page themselves first before we force the visit.
    time.sleep(10)

    c = Client()

    loaded_pages = UnsubmittedTimeoutPage.objects.filter(
        app_name=app_name,
        page_index=page_index,
        player_pk__in=set(player_pk_set)
    )
    visited_pk_set = set([page.player_pk for page in loaded_pages])
    unvisited_pk_set = player_pk_set - visited_pk_set

    unvisited_players = get_models_module(app_name).Player.objects.filter(pk__in=unvisited_pk_set)
    for player in unvisited_players:
        # for simplicity of programming, we can just GET the player's start URL, because oTree auto-redirects to the page the user should be on
        c.get(player._start_url(), follow=True)



