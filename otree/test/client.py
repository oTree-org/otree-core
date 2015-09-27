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
import urlparse
import decimal
import logging
import abc
from importlib import import_module

from django import test

from easymoney import Money as Currency

from otree import constants_internal

# =============================================================================
# LOGGER
# =============================================================================

logger = logging.getLogger(__name__)


def refresh_from_db(obj):
    return type(obj).objects.get(pk=obj.pk)

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
        if not end:
            # don't need to check if it has errors because
            # nothing was submitted
            return False

        has_errors = self.bot.page_redisplayed_with_errors()

        if self.input_is_valid and has_errors:
            form = self.bot.response.context_data['form']
            errors = [
                "{}: {}".format(k, repr(v)) for k, v in form.errors.items()]
            msg = ('Input was rejected.\nPath: {}\nErrors: {}\n').format(
                self.bot.path, errors)
            raise AssertionError(msg)
        elif not self.input_is_valid and not has_errors:
            msg = "Invalid input was accepted. Path: {}, params: {}".format(
                self.bot.path, self.data)
            raise AssertionError(msg)
        return True


# =============================================================================
# BASE CLIENT
# =============================================================================

class ParticipantBot(test.Client):

    __metaclass__ = abc.ABCMeta

    def __init__(self, participant, **kwargs):
        self.participant = participant
        self.response = None
        self.url = None
        self.path = None
        self.num_bots = self.participant.session.config['num_bots']
        self.submits = []
        super(ParticipantBot, self).__init__()

        self.player_bots = []
        for player in self.participant.get_players():
            try:
                test_module_name = '{}.tests'.format(
                    player.subsession.app_name
                )
                test_module = import_module(test_module_name)
                logger.info("Found test '{}'".format(test_module_name))
            except ImportError as err:
                self.fail(unicode(err))

            player_bot = test_module.PlayerBot(
                player=player,
                participant_bot=self
            )
            self.player_bots.append(player_bot)

    def start(self):
        self.response = self.get(
            self.participant._start_url(),
            follow=True
        )
        self.set_path()
        self.check_200()
        for player_bot in self.player_bots:
            player_bot.play_round()

    def stop(self):
        """Execute the validate_play after all runs are ended"""
        for player_bot in self.player_bots:
            player_bot._validate_play()

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
        return re.match(ViewClass.url_pattern(), self.path.lstrip('/'))

    def assert_is_on(self, ViewClass):
        if not self.is_on(ViewClass):
            msg = "Expected page: {}, Actual page: {}".format(
                ViewClass.__name__, self.path)
            raise AssertionError(msg)

    def on_wait_page(self):
        return (
            self.response.get(constants_internal.wait_page_http_header) ==
            constants_internal.get_param_truth_value)

    def page_redisplayed_with_errors(self):
        header = constants_internal.redisplay_with_errors_http_header
        truth_value = constants_internal.get_param_truth_value
        return (
            self.response.get(header) == truth_value)

    def set_path(self):
        try:
            self.url = self.response.redirect_chain[-1][0]
            self.path = urlparse.urlsplit(self.url).path
        except IndexError:
            pass

    def submit(self, ViewClass, param_dict=None):
        sbmt = Submit(
            bot=self, ViewClass=ViewClass,
            input_is_valid=True, data=param_dict)
        self.submits.append(sbmt)

    def submit_invalid(self, ViewClass, param_dict=None):
        '''this method lets you intentionally submit with invalid
        input to ensure it's correctly rejected

        '''
        sbmt = Submit(
            bot=self, ViewClass=ViewClass,
            input_is_valid=False, data=param_dict)
        self.submits.append(sbmt)


# =============================================================================
# PLAYER BOT CLASS
# =============================================================================

class PlayerBot(object):

    def __init__(self, player, participant_bot, **kwargs):

        self.participant_bot = participant_bot
        self.participant = player.participant
        self.player = player
        self.group = player.group
        self.subsession = player.subsession

        if self.player.group is None:
            msg = "Player still not in group"
            raise AssertionError(msg)

    @abc.abstractmethod
    def play_round(self):
        raise NotImplementedError()

    def validate_play(self):
        raise NotImplementedError()

    def _validate_play(self):
        self._refresh_models()
        self.validate_play()

    def _refresh_models(self):
        self.player = refresh_from_db(self.player)
        # need to do self.player.group because the player might have been
        # reassigned to a new group during the subsession
        self.group = refresh_from_db(self.player.group)
        self.subsession = refresh_from_db(self.subsession)

    def submit(self, ViewClass, param_dict=None):
        self.participant_bot.submit(ViewClass, param_dict)

    def submit_invalid(self, ViewClass, param_dict=None):
        self.participant_bot.submit_invalid(ViewClass, param_dict)
