import django.test.client
import re
import time
import ptree.constants
from urlparse import urlsplit
import sys

MAX_SECONDS_TO_WAIT = 10

class BaseClient(django.test.client.Client):

    def __init__(self):
        self.response = None
        self.path = None
        super(BaseClient, self).__init__()

    def _play(self, failure_queue):
        self.failure_queue = failure_queue
        try:
            self.play()
        except:
            self.failure_queue.put(ptree.constants.failure)
            raise

    def play(self):
        raise NotImplementedError()

    def start(self):
        # do i need to parse out the GET data into the data arg?
        self.response = self.get(self.user.start_url(), follow=True)
        self.set_path()
        self.assert_200()

    def assert_200(self):
        if self.response.status_code != 200:
            raise Exception('Response status code: {} (expected 200)'.format(self.response.status_code))

    def is_on(self, ViewClass):
        _, _, path, _, _ = urlsplit(self.path)
        return re.match(ViewClass.url_pattern(), path.lstrip('/'))

    def assert_is_on(self, ViewClass):
        if not self.is_on(ViewClass):
            raise Exception('Expected page: {}, Actual page: {}'.format(
                ViewClass.url_pattern(),
                self.path
        ))

    def submit(self, ViewClass, data=None):

        data = data or {}
        self.assert_is_on(ViewClass)
        # if it's a waiting page, wait N seconds and retry
        first_wait_page_try_time = time.time()
        while self.on_wait_page():
            print '{} (wait page)'.format(self.path)
            time.sleep(1) #quicker sleep since it's bots playing the game
            self.retry_wait_page()
            if time.time() - first_wait_page_try_time > MAX_SECONDS_TO_WAIT:
                raise Exception('Participant appears to be stuck on waiting page (waiting for over {} seconds)'.format(MAX_SECONDS_TO_WAIT))
        if data:
            print '{}, {}'.format(self.path, data)
        else:
            print self.path
        self.response = self.post(self.path, data, follow=True)
        self.assert_200()
        self.set_path()

        if self.page_redisplayed_with_errors():
            errors = ['{}: {}'.format(key, repr(value)) for key, value in self.response.context_data['form_or_formset'].errors.items()]
            raise Exception(
                ('Input was rejected.\n'
                'Path: {}\n'
                'Errors: {}\n').format(self.path, errors))


    def submit_with_invalid_input(self, ViewClass, data=None):
        self.submit(ViewClass, data)

        if not self.page_redisplayed_with_errors():
            raise Exception('Invalid input was accepted. Path: {}, data: {}'.format(self.path, data))

    def retry_wait_page(self):
        # check if another thread has failed.
        if self.failure_queue.qsize() > 0:
            sys.exit(0)
        self.response = self.get(self.path, follow=True)
        self.assert_200()
        self.set_path()

    def on_wait_page(self):
        return self.response.get(ptree.constants.wait_page_http_header) == ptree.constants.get_param_truth_value

    def page_redisplayed_with_errors(self):
        return self.response.get(ptree.constants.redisplay_with_errors_http_header) == ptree.constants.get_param_truth_value

    def set_path(self):
        try:
            self.path = self.response.redirect_chain[-1][0]
        except IndexError:
            pass


class ParticipantBot(BaseClient):

    def __init__(self, user):
        self.user = user
        self.participant = user
        self.match = self.participant.match
        self.treatment = self.participant.treatment
        # we assume the experimenter has assigned everyone to a treatment
        assert self.match and self.treatment
        self.subsession = self.participant.subsession
        super(ParticipantBot, self).__init__()

class ExperimenterBot(BaseClient):

    def __init__(self, subsession):
        self.user = subsession.experimenter
        self.subsession = subsession
        super(ExperimenterBot, self).__init__()