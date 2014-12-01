from otree.db import models
import time

from otree.common_internal import get_models_module
from otree import constants
from celery import task

from django.test import Client

@task()
def submit_expired_url(url):

    c = Client()
    c.post(url, data={constants.auto_submit: True}, follow=True)

@task()
def ensure_pages_visited(app_name, player_pk_set, wait_page_index):
    """
    This is necessary when a wait page is followed by a timeout page.
    We can't guarantee the user's browser will properly continue to poll the wait page and get redirected,
    so after a grace period we load the page automatically, to kick off the expiration timer of the timeout page."""

    # grace period because we want to give the user a chance to visit the page themselves first before we force the visit.
    time.sleep(10)

    c = Client()

    #FIXME: no longer applies to players
    unvisited_players = get_models_module(app_name).Player.objects.filter(
        pk__in=player_pk_set,
        _index_in_pages__lte=wait_page_index,
    )

    #FIXME 2014-12-01: not working with views refactor
    """
    for player in unvisited_players:
        # for simplicity of programming, we can just GET the player's start URL, because oTree auto-redirects to the page the user should be on
        c.get(player._start_url(), follow=True)
    """