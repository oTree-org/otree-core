import django.test.client
import re
import time
import ptree.constants

# should also implement experimenter client

class BaseClient(django.test.client.Client):

    def __init__(self, user, test_case):
        self.user = user
        self.test_case = test_case
        self.response = None
        self.args = None
        super(BaseClient, self).__init__()

    def start(self):
        # do i need to parse out the GET data into the data arg?
        self.get(self.user.start_url(), follow=True)

    def submit(self, ViewClass, data=None):
        # if it's a waiting page, wait N seconds and retry
        while self.on_wait_page():
            time.sleep(5)
            self.retry_wait_page()
        assert re.match(ViewClass.url_pattern(), self.path())
        self.response = self.post(self.path(), data, follow=True)
        self.test_case.assertEqual(self.response.status_code, 200)

    def retry_wait_page(self):
        self.response = self.get(self.path(), follow=True)

    def on_wait_page(self):
        return self.response.get(ptree.constants.wait_page_http_header)

    def path(self):
        return self.response.redirect_chain[-1][0]

class ExperimenterClient(BaseClient):

    def __init__(self, subsession):
        self.user = subsession.experimenter
        self.response = None
        self.args = None
        super(BaseClient, self).__init__()

    def start(self):
        super(ExperimenterClient, self).start()
        # initialize

Client = BaseClient