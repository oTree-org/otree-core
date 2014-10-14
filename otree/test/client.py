import django.test.client
import re
import time
import otree.constants
from urlparse import urlsplit, urljoin
import sys
from django.utils.importlib import import_module
from otree.user.models import Experimenter
import random
import coverage
from easymoney import Money
from decimal import Decimal

MAX_SECONDS_TO_WAIT = 20

SERVER_URL = 'http://127.0.0.1:8000'

class BaseClient(django.test.client.Client):

    def __init__(self, **kwargs):
        self.response = None
        self.url = None
        self.path = None
        super(BaseClient, self).__init__()

    def get(self, path, data={}, follow=False, **extra):
        response = super(BaseClient, self).get(path, data, follow, **extra)
        if response.status_code == 500:
            print 'hello'
        return response

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
        self.assert_200()

    def assert_200(self):
        if self.response.status_code != 200:
            raise Exception('Response status code: {} (expected 200)'.format(self.response.status_code))

    def is_on(self, ViewClass):
        return re.match(ViewClass.url_pattern(), self.path.lstrip('/'))

    def assert_is_on(self, ViewClass):
        if not self.is_on(ViewClass):
            raise Exception('Expected page: {}, Actual page: {}'.format(
                ViewClass.__name__,
                self.path
        ))


    def _submit_core(self, ViewClass, data=None):
        data = data or {}
        for key in data:
            if isinstance(data[key], Money):
                data[key] = Decimal(data[key])
        # if it's a waiting page, wait N seconds and retry
        first_wait_page_try_time = time.time()
        while self.on_wait_page():
            print '{} (wait page)'.format(self.path)
            time.sleep(1) #quicker sleep since it's bots playing the game
            self.retry_wait_page()
            if time.time() - first_wait_page_try_time > MAX_SECONDS_TO_WAIT:
                raise Exception('Player appears to be stuck on waiting page (waiting for over {} seconds)'.format(MAX_SECONDS_TO_WAIT))
        self.assert_is_on(ViewClass)
        if data:
            print '{}, {}'.format(self.path, data)
        else:
            print self.path
        self.response = self.post(self.url, data, follow=True)
        self.assert_200()
        self.set_path()

    def submit(self, ViewClass, param_dict=None):
        self._submit_with_valid_input(ViewClass, param_dict)

    def _submit_with_valid_input(self, ViewClass, data=None):
        self._submit_core(ViewClass, data)

        if self.page_redisplayed_with_errors():
            errors = ['{}: {}'.format(key, repr(value)) for key, value in self.response.context_data['form'].errors.items()]
            raise Exception(
                ('Input was rejected.\n'
                'Path: {}\n'
                'Errors: {}\n').format(self.path, errors))

    def submit_with_invalid_input(self, ViewClass, param_dict=None):
        self.submit(ViewClass, param_dict)

        if not self.page_redisplayed_with_errors():
            raise Exception('Invalid input was accepted. Path: {}, params: {}'.format(self.path, param_dict))


    def retry_wait_page(self):
        # check if another thread has failed.
        if self.failure_queue.qsize() > 0:
            sys.exit(0)
        self.response = self.get(self.url, follow=True)
        self.assert_200()
        self.set_path()

    def on_wait_page(self):
        return self.response.get(otree.constants.wait_page_http_header) == otree.constants.get_param_truth_value

    def page_redisplayed_with_errors(self):
        return self.response.get(otree.constants.redisplay_with_errors_http_header) == otree.constants.get_param_truth_value

    def set_path(self):
        try:
            self.url = self.response.redirect_chain[-1][0]
            self.path = urlsplit(self.url).path
        except IndexError:
            pass


class PlayerBot(BaseClient):

    @property
    def player(self):
        """this needs to be a property because asserts require refreshing from the DB"""
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

    def _play(self, failure_queue):
        super(PlayerBot, self)._play(failure_queue)
        if self.player.payoff is None:
            self.failure_queue.put(True)
            raise Exception('Player "{}": payoff is still None at the end of the subsession.'.format(self.player.participant.code))


    def __init__(self, user, **kwargs):
        player = user
        app_label = user.subsession.app_name
        models_module = import_module('{}.models'.format(app_label))

        self._PlayerClass = models_module.Player
        self._GroupClass = models_module.Group
        self._SubsessionClass = models_module.Subsession
        self._UserClass = self._PlayerClass

        assert player.group

        self._player_id = player.id
        self._group_id = player.group.id
        self._subsession_id = player.subsession.id

        super(PlayerBot, self).__init__(**kwargs)

class ExperimenterBot(BaseClient):

    @property
    def subsession(self):
        return self._SubsessionClass.objects.get(id=self._subsession_id)

    # it's OK for play to be left blank because the experimenter might not have anything to do
    def play(self):
        pass

    @property
    def _user(self):
        return Experimenter.objects.get(id=self._experimenter_id)

    def __init__(self, subsession, **kwargs):
        self._SubsessionClass = type(subsession)
        self._subsession_id = subsession.id
        self._experimenter_id = subsession._experimenter.id

        super(ExperimenterBot, self).__init__(**kwargs)