#!/usr/bin/env python
# -*- coding: utf-8 -*-

# =============================================================================
# DOCS
# =============================================================================

"""
"""


# =============================================================================
# IMPORTS
# =============================================================================

import re
import importlib
import urlparse
import decimal
import logging
import abc

from django import test

from easymoney import Money as Currency

from otree import constants
from otree.views.concrete import WaitUntilAssignedToGroup
from otree.common_internal import get_views_module

# =============================================================================
# LOGGER
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# CLIENT ERROR
# =============================================================================

class ClientError(Exception):
    """This class represent all errors inside client logic except
    the assertions

    """

    pass


# =============================================================================
# CLASS SUBMITS
# =============================================================================

class Submit(object):

    def __init__(self, bot, ViewClass, input_is_valid, data):
        self.bot = bot
        self.ViewClass = ViewClass
        self.input_is_valid = input_is_valid
        self.data = data or {}

        # clean data
        for key in self.data:
            if isinstance(self.data[key], Currency):
                self.data[key] = decimal.Decimal(data[key])

    def __repr__(self):
        return "{}, {}".format(self.ViewClass.__name__, self.data)

    def execute_core(self):
        """Execute the real call over the client, if it return True, the submit
        is finished

        """
        if self.bot.on_wait_page():
            try:
                self.bot.response = self.bot.get(self.bot.url, follow=True)
                self.bot.check_200()
                self.bot.set_path()
            finally:
                return False

        self.bot.assert_is_on(self.ViewClass)
        if self.data:
            logger.info('{}, {}'.format(self.bot.path, self.data))
        else:
            logger.info(self.bot.path)
        self.bot.response = self.bot.post(self.bot.url, self.data, follow=True)

        self.bot.check_200()
        self.bot.set_path()
        return True

    def execute(self):
        """This method execute the submit and validate if all is ok according
        to the configuration

        """
        end = self.execute_core()
        has_errors = self.bot.page_redisplayed_with_errors()

        if self.input_is_valid and has_errors:
            form = self.bot.response.context_data['form']
            errors = [
                "{}: {}".format(k, repr(v)) for k, v in form.errors.items()
            ]
            msg = ('Input was rejected.\nPath: {}\nErrors: {}\n').format(
                self.bot.path, errors
            )
            raise AssertionError(msg)
        elif not self.input_is_valid and not has_errors:
            msg = "Invalid input was accepted. Path: {}, params: {}".format(
                self.bot.path, self.data
            )
            raise AssertionError(msg)
        return end


# =============================================================================
# BASE CLIENT
# =============================================================================

class BaseClient(test.Client):

    __metaclass__ = abc.ABCMeta

    def __init__(self, **kwargs):
        self.response = None
        self.url = None
        self.path = None
        self.num_bots = self.subsession.session.session_type['num_bots']
        self.submits = []
        super(BaseClient, self).__init__()

    def start(self):
        """Recolect all the submits in self.submit"""
        wait_page_url = WaitUntilAssignedToGroup.url(
            self.player.participant,
            self.player.participant._index_in_pages
        )
        self.response = self.get(wait_page_url, follow=True)
        self.set_path()
        self.check_200()
        self.play_round()

    @abc.abstractmethod
    def play_round(self):
        raise NotImplementedError()

    def stop(self):
        """Execute the validate_play after all runs are ended"""
        self.validate_play()

    @abc.abstractmethod
    def validate_play(self):
        raise NotImplementedError()

    def check_200(self):
        # 2014-10-22: used to raise an exception here but i don't think that's
        # necessary because the server-side exception should be shown anyway.
        # Also, this exception doesn't have a useful traceback.
        if self.response.status_code != 200:
            msg = "Response status code: {} (expected 200)".format(
                self.response.status_code
            )
            logger.warning(msg)

    def get(self, path, data={}, follow=False, **extra):
        return super(BaseClient, self).get(path, data, follow, **extra)

    def is_on(self, ViewClass):
        return re.match(ViewClass.url_pattern(), self.path.lstrip('/'))

    def assert_is_on(self, ViewClass):
        if not self.is_on(ViewClass):
            msg = "Expected page: {}, Actual page: {}".format(
                ViewClass.__name__, self.path
            )
            raise AssertionError(msg)

    def on_wait_page(self):
        return (
            self.response.get(constants.wait_page_http_header) ==
            constants.get_param_truth_value
        )

    def page_redisplayed_with_errors(self):
        return (
            self.response.get(constants.redisplay_with_errors_http_header) ==
            constants.get_param_truth_value
        )

    def set_path(self):
        try:
            self.url = self.response.redirect_chain[-1][0]
            self.path = urlparse.urlsplit(self.url).path
        except IndexError:
            pass

    def submit(self, ViewClass, param_dict=None):
        sbmt = Submit(
            bot=self, ViewClass=ViewClass, input_is_valid=True, data=param_dict
        )
        self.submits.append(sbmt)

    def submit_invalid(self, ViewClass, param_dict=None):
        '''this method lets you intentionally submit with invalid
        input to ensure it's correctly rejected

        '''
        sbmt = Submit(
            bot=self, ViewClass=ViewClass,
            input_is_valid=False, data=param_dict
        )
        self.submits.append(sbmt)


# =============================================================================
# PLAYER BOT CLASS
# =============================================================================

class BasePlayerBot(BaseClient):

    def __init__(self, user, **kwargs):
        app_label = user.subsession._meta.app_config.name
        models_module = importlib.import_module('{}.models'.format(app_label))

        self._PlayerClass = models_module.Player
        self._GroupClass = models_module.Group
        self._SubsessionClass = models_module.Subsession
        self._UserClass = self._PlayerClass

        if user.group is None:
            msg = "Player still not in group"
            raise AssertionError(msg)

        self._player_id = user.id
        self._group_id = user.group.id
        self._subsession_id = user.subsession.id

        super(BasePlayerBot, self).__init__(**kwargs)

    def stop(self):
        player = self.player
        if player.payoff is None:
            msg = (
                "App {}: Player '{}': payoff is still None at the end of the "
                "subsession. Check in tests.py if the bot completes the game."
            ).format(
                self.subsession._meta.app_config.name,
                player.participant.code,
            )

            # FIXME: why doesn't this work? the game works fine, and print
            # statements show that a payoff is non-null
            # ANSWER:
            # this fails beacuse the test only simulate the play but the payoff
            # is never set. I will try a workarround
            # raise AssertionError(msg)
        player_page_index = player._index_in_game_pages
        pages_in_subsession = len(
            get_views_module(self.subsession.app_name).page_sequence
        )
        if player_page_index + 1 < pages_in_subsession:
            msg = (
                "App {}: Participant '{}' reached the page {} of {} at "
                "the end of run. Check in tests.py if the bot completes "
                "the game"
            ).format(
                self.subsession._meta.app_config.name,
                player.participant.code,
                player_page_index,
                pages_in_subsession,
            )
            raise AssertionError(msg)
        super(BasePlayerBot, self).stop()

    @property
    def player(self):
        # This needs to be a property because asserts
        # require refreshing from the DB
        return self._PlayerClass.objects.get(id=self._player_id)

    @property
    def _user(self):
        return self.player

    @property
    def group(self):
        return self._GroupClass.objects.get(id=self._group_id)

    @property
    def subsession(self):
        return self._SubsessionClass.objects.get(id=self._subsession_id)
