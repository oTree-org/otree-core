#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import decimal
import logging
import abc
import six
from importlib import import_module
from six.moves import urllib
from django import test
import json
from easymoney import Money as Currency
from django.core.urlresolvers import resolve
from otree import constants_internal

from otree.common_internal import get_dotted_name, get_bots_module

logger = logging.getLogger('otree.bots')


class Pause(object):

    def __init__(self, seconds):
        self.seconds = seconds

def MustFail(PageClass, submission_dict=None):
    '''lets you intentionally submit with invalid
    input to ensure it's correctly rejected'''

    submission_dict = submission_dict or {}
    submission_dict.update({'must_fail': True})
    return (PageClass, submission_dict)


def submission_as_dict(submission):

    post_data = {}

    # TODO: validate that user isn't trying to submit a WaitPage,
    # or other possible mistakes
    # had a circular import problem when this was a module-level import
    # moving it here for now...
    from otree.views import Page
    if isinstance(submission, (list, tuple)):
        PageClass = submission[0]
        if len(submission) == 2:
            post_data = submission[1] or {}
    else:
        PageClass = submission

    for key in post_data:
        if isinstance(post_data[key], Currency):
            # because must be json serializable for Huey
            post_data[key] = str(decimal.Decimal(post_data[key]))

    return {
        'page_class': PageClass,
        'page_class_dotted': get_dotted_name(PageClass),
        'post_data': post_data
    }


def is_wait_page(response):
    return (
        response.get(constants_internal.wait_page_http_header) ==
        constants_internal.get_param_truth_value)


def refresh_from_db(obj):
    return type(obj).objects.get(pk=obj.pk)


class ParticipantBot(six.with_metaclass(abc.ABCMeta, test.Client)):

    def __init__(
            self, participant, max_wait_seconds=None,
            **kwargs):
        self.participant = participant
        self.response = None
        self.url = None
        self.path = None
        self.num_bots = self.participant.session.config['num_bots']
        self.submits = None
        self.max_wait_seconds = max_wait_seconds
        super(ParticipantBot, self).__init__()

        self.player_bots = []
        for player in self.participant.get_players():
            bots_module = get_bots_module(player._meta.app_config.name)
            player_bot = bots_module.PlayerBot(
                player=player,
                participant_bot=self,
            )
            self.player_bots.append(player_bot)
        self.submits_generator = self.get_submits()

    def open_start_url(self):
        self.response = self.get(
            self.participant._start_url(),
            follow=True
        )
        self.set_path()
        self.check_200()

    def get_submits(self):
        for player_bot in self.player_bots:
            # play_round populates legacy submit list
            generator = player_bot.play_round()
            if player_bot._legacy_submit_list:
                for submission in player_bot._legacy_submit_list:
                    yield submission
            else:
                try:
                    for submission in generator:
                        yield submission
                # handle the case where it's empty
                except TypeError as exc:
                    if 'is not iterable' in str(exc):
                        raise StopIteration
                    raise

    def check_200(self):
        # 2014-10-22: used to raise an exception here but i don't think that's
        # necessary because the server-side exception should be shown anyway.
        # Also, this exception doesn't have a useful traceback.
        if self.response.status_code != 200:
            msg = "Response status code: {} (expected 200)".format(
                self.response.status_code)
            logger.warning(msg)

    def get(self, path, data={}, follow=False, **extra):
        return super(ParticipantBot, self).get(path, data, follow, **extra)

    def is_on(self, ViewClass):
        return ViewClass.url_name() == resolve(self.path).url_name

    def assert_is_on(self, ViewClass):
        if not self.is_on(ViewClass):
            msg = "Expected page: {}, Actual page: {}".format(
                ViewClass.__name__, self.path)
            raise AssertionError(msg)

    def on_wait_page(self):
        # if the existing response was a form page, it will still be...
        # no need to check again
        if not is_wait_page(self.response):
            return False

        # however, wait pages can turn into regular pages, so let's try again
        self.response = self.get(self.url, follow=True)
        self.check_200()
        self.set_path()
        return is_wait_page(self.response)

    def set_path(self):
        try:
            self.url = self.response.redirect_chain[-1][0]
            self.path = urllib.parse.urlsplit(self.url).path
        except IndexError:
            pass

    def submit(self, submission):

        submission = submission_as_dict(submission)
        PageClass = submission['page_class']
        post_data = submission['post_data']

        # TODO: get assert_is_on working
        self.assert_is_on(PageClass)
        if post_data:
            logger.info('{}, {}'.format(self.path, post_data))
        else:
            logger.info(self.path)

        self.response = self.post(self.url, post_data, follow=True)

        self.check_200()
        self.set_path()


class PlayerBot(object):

    def __init__(self, player, participant_bot, **kwargs):

        self.participant_bot = participant_bot
        self._cached_player = player
        self._cached_group = player.group
        self._cached_subsession = player.subsession
        self._cached_participant = player.participant
        self._cached_session = player.session

        self._legacy_submit_list = []

        bots_module = import_module(self.__module__)


        mode_number = self._cached_session._bot_case_number
        CASES = getattr(bots_module, 'CASES', [])
        if len(CASES) >= 1:
            self.case = CASES[mode_number % len(CASES)]
        else:
            self.case = None

    def play_round(self):
        pass

    @property
    def player(self):
        return refresh_from_db(self._cached_player)

    @property
    def group(self):
        return refresh_from_db(self._cached_group)

    @property
    def subsession(self):
        return refresh_from_db(self._cached_subsession)

    @property
    def session(self):
        return refresh_from_db(self._cached_session)

    @property
    def participant(self):
        return refresh_from_db(self._cached_participant)

    def submit(self, ViewClass, param_dict=None):
        self._legacy_submit_list.append((ViewClass, param_dict))

    def submit_invalid(self, ViewClass, param_dict=None):
        # simpler to make this a no-op, it makes porting to yield easier
        # then we can just do a search-and-replace
        # self._legacy_submit_list.append((ViewClass, param_dict, 'invalid'))
        pass

    def pause(self, seconds):
        '''
        should i call it sleep or pause? sleep is better known,
        but people might mistakenly confuse it with time.sleep(),
        which blocks the thread. if this eventually becomes a function
        rather than a method, it will be invoked as sleep(), which could
        lead to people importing from the time module.
        '''
        return Pause(seconds)
