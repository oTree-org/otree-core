#!/usr/bin/env python
# -*- coding: utf-8 -*-

import django.test

from celery import shared_task

from otree import constants_internal


@shared_task
def submit_expired_url(url):

    c = django.test.Client()
    c.post(url, data={constants_internal.auto_submit: True}, follow=True)


@shared_task
def ensure_pages_visited(participant_pk_set, wait_page_index):

    """
    This is necessary when a wait page is followed by a timeout page.
    We can't guarantee the user's browser will properly continue to poll
    the wait page and get redirected, so after a grace period we load the page
    automatically, to kick off the expiration timer of the timeout page.

    """

    from otree.models.session import Participant
    c = django.test.Client()

    unvisited_participants = Participant.objects.filter(
        pk__in=participant_pk_set,
        _index_in_pages__lte=wait_page_index,
    )

    for participant in unvisited_participants:
        # we can assume _current_form_page_url is not null because
        # the wait page was visited
        c.get(participant._current_form_page_url, follow=True)
