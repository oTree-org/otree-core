import django.test.client
import re
import time
import ptree.constants
from urlparse import urlsplit

class BaseClient(django.test.client.Client):

    def __init__(self):
        self.response = None
        self.path = None
        super(BaseClient, self).__init__()

    def _play(self, completion_queue, settings_queue):

        try:
            self.play()
        except:
            completion_queue.put(ptree.constants.failure)
        else:
            completion_queue.put(ptree.constants.success)

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
        print self.path
        data = data or {}
        self.assert_is_on(ViewClass)
        # if it's a waiting page, wait N seconds and retry
        while self.on_wait_page():
            print 'on wait page. path: {}'.format(self.path)
            time.sleep(1) #quicker sleep since it's bots playing the game
            self.retry_wait_page()

        self.response = self.post(self.path, data, follow=True)
        self.assert_200()
        self.set_path()

    def submit_with_invalid_input(self, ViewClass, data=None):
        self.submit(ViewClass, data)

        if not self.page_redisplayed_with_errors():
            raise Exception('Expected invalid input to be rejected, but instead input was accepted: {}'.format(self.path))

    def retry_wait_page(self):
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