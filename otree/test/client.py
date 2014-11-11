#!/usr/bin/env python
# -*- coding: utf-8 -*-

#==============================================================================
# DOCS
#==============================================================================

"""
"""


#==============================================================================
# IMPORTS
#==============================================================================

import sys
import re
import time
import importlib
import urlparse
import decimal
import logging

from django import test

from easymoney import Money as Currency

from otree import constants
from otree.models.user import Experimenter


#==============================================================================
# CONSTANTS
#==============================================================================

SECONDS_TO_WAIT_PER_BOT = 1


#==============================================================================
# LOGGER
#==============================================================================

logger = logging.getLogger(__name__)


#==============================================================================
# CLIENT ERROR
#==============================================================================

class ClientError(Exception):
    """This class represent all errors inside client logic except
    the assertions

    """

    pass


#==============================================================================
# BASE CLIENT
#==============================================================================

class BaseClient(test.Client):

    def __init__(self, **kwargs):
        self.response = None
        self.url = None
        self.path = None
        self.num_bots = self.subsession.session.type().num_bots
        super(BaseClient, self).__init__()

    def _submit_core(self, ViewClass, data=None):
        data = data or {}
        for key in data:
            if isinstance(data[key], Currency):
                data[key] = decimal.Decimal(data[key])

        # if it's a waiting page, wait N seconds and retry
        first_wait_page_try_time = time.time()
        while self.on_wait_page():
            logger.info('{} (wait page)'.format(self.path))

            #quicker sleep since it's bots playing the game
            time.sleep(1)
            self.retry_wait_page()
            seconds_to_wait = SECONDS_TO_WAIT_PER_BOT * self.num_bots
            if time.time() - first_wait_page_try_time > seconds_to_wait:
                msg = ("Player appears to be stuck on waiting page "
                       "(waiting for over {} seconds)")
                raise ClientError(msg.format(seconds_to_wait))
        self.assert_is_on(ViewClass)
        if data:
            logger.info('{}, {}'.format(self.path, data))
        else:
            logger.info(self.path)
        self.response = self.post(self.url, data, follow=True)
        self.check_200()
        self.set_path()

    def _submit_with_valid_input(self, ViewClass, data=None):
        self._submit_core(ViewClass, data)

        if self.page_redisplayed_with_errors():
            errors = [
                "{}: {}".format(k, repr(v))
                for k, v in self.response.context_data['form'].errors.items()
            ]
            msg = ('Input was rejected.\nPath: {}\nErrors: {}\n').format(
                self.path, errors
            )
            raise AssertionError(msg)

    def _play(self, failure_queue):

        self.failure_queue = failure_queue
        try:
            self.play()
        except:
            self.failure_queue.put(True)
            raise

    def play(self):
        raise NotImplementedError()

    def start(self):
        # do i need to parse out the GET data into the data arg?
        self.response = self.get(self._user._start_url(), follow=True)
        self.set_path()
        self.check_200()

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

    def submit(self, ViewClass, param_dict=None):
        self._submit_with_valid_input(ViewClass, param_dict)

    def submit_with_invalid_input(self, ViewClass, param_dict=None):
        self.submit(ViewClass, param_dict)
        if not self.page_redisplayed_with_errors():
            msg = "Invalid input was accepted. Path: {}, params: {}".format(
                self.path, param_dict
            )
            raise AssertionError(msg)

    def retry_wait_page(self):
        # check if another thread has failed.
        if self.failure_queue.qsize() > 0:
            sys.exit(0)
        self.response = self.get(self.url, follow=True)
        self.check_200()
        self.set_path()

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


#==============================================================================
# PLAYER BOT CLASS
#==============================================================================

class PlayerBot(BaseClient):

    def __init__(self, user, **kwargs):
        player = user
        app_label = user.subsession.app_name
        models_module = importlib.import_module('{}.models'.format(app_label))

        self._PlayerClass = models_module.Player
        self._GroupClass = models_module.Group
        self._SubsessionClass = models_module.Subsession
        self._UserClass = self._PlayerClass

        if player.group is None:
            msg = "Player still not in group"
            raise AssertionError(msg)

        self._player_id = player.id
        self._group_id = player.group.id
        self._subsession_id = player.subsession.id

        super(PlayerBot, self).__init__(**kwargs)

    def _play(self, failure_queue):
        super(PlayerBot, self)._play(failure_queue)
        time.sleep(1)
        if self.player.payoff is None:
            self.failure_queue.put(True)
            msg = (
                "App {}: Player '{}': payoff is still None at the end of the "
                "subsession. Check in tests.py if the bot completes the game."
            ).format(
                self.subsession._meta.app_label,
                self.player.participant.code
            )
            raise ClientError(msg)

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


#==============================================================================
# ESPERIMENT BOT CLASS
#==============================================================================

# Currently not being used, but we may start using this again soon
class ExperimenterBot(BaseClient):

    def __init__(self, subsession, **kwargs):
        self._SubsessionClass = type(subsession)
        self._subsession_id = subsession.id
        self._experimenter_id = subsession._experimenter.id

        super(ExperimenterBot, self).__init__(**kwargs)

    def play(self):
        # it's OK for play to be left blank because the experimenter might
        # not have anything to do
        pass

    @property
    def subsession(self):
        return self._SubsessionClass.objects.get(id=self._subsession_id)

    @property
    def _user(self):
        return Experimenter.objects.get(id=self._experimenter_id)
