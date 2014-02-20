import django.test.client
import re
import time
import ptree.constants
from urlparse import urlsplit

# should also implement experimenter client

class BaseClient(django.test.client.Client):

    def __init__(self):
        self.response = None
        super(BaseClient, self).__init__()

    def play(self):
        raise NotImplementedError()

    def start(self):
        # do i need to parse out the GET data into the data arg?
        self.response = self.get(self.user.start_url(), follow=True)
        self.assert_200()

    def assert_200(self):
        if self.response.status_code != 200:
            raise AssertionError('Response status code: {} (expected 200)'.format(self.response.status_code))

    def is_on(self, ViewClass):
        _, _, path, _, _ = urlsplit(self.path())
        return re.match(ViewClass.url_pattern(), path.lstrip('/'))

    def assert_is_on(self, ViewClass):
        if not self.is_on(ViewClass):
            raise AssertionError('Expected page: {}, Actual page: {}'.format(
                ViewClass.url_pattern(),
                self.path()
        ))

    def submit(self, ViewClass, data=None):
        path = self.path()
        print path
        data = data or {}
        self.assert_is_on(ViewClass)
        # if it's a waiting page, wait N seconds and retry
        while self.on_wait_page():
            print 'on wait page. path: {}'.format(self.path())
            time.sleep(1) #quicker sleep since it's bots playing the game
            self.retry_wait_page()

        self.response = self.post(path, data, follow=True)
        self.assert_200()

    def retry_wait_page(self):
        self.response = self.get(self.path(), follow=True)
        self.assert_200()

    def on_wait_page(self):
        return self.response.get(ptree.constants.wait_page_http_header) == ptree.constants.get_param_truth_value

    def path(self):
        try:
            return self.response.redirect_chain[-1][0]
        except IndexError:
            raise IndexError('redirect chain: {}'.format(self.response.redirect_chain))

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