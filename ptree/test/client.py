import django.test.client
import re
import time
import ptree.constants
from urlparse import urlsplit, urljoin
import sys
from selenium import webdriver
import os.path
import csv

MAX_SECONDS_TO_WAIT = 10

SERVER_URL = 'http://127.0.0.1:8000'

class BaseClient(django.test.client.Client):

    def __init__(self, **kwargs):
        self.response = None
        self.url = None
        self.path = None
        self.take_screenshots = kwargs['take_screenshots']
        self.screenshot_dir = kwargs.get('screenshot_dir')
        if self.take_screenshots:
            self.launch_browser_for_screenshots()
            csv_file = open(os.path.join(self.screenshot_dir, 'Index.csv'))
            csv_fields = [
                'filename',
                'participant',
                'app_label',
                'subsession_id',
                'page_name',
                #'page_index'
            ]
            self.screenshot_csv_writer = csv.DictWriter(csv_file, csv_fields)
            self.index_of_current_screenshot = 0
        super(BaseClient, self).__init__()

    def launch_browser_for_screenshots(self):
        self.browser = webdriver.Firefox()
        self.browser.get(urljoin(SERVER_URL, self.user._start_url()))

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
        self.response = self.get(self.user._start_url(), follow=True)
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
                ViewClass.url_pattern(),
                self.path
        ))


    def screenshot(self, ViewClass):

        self.browser.get(urljoin(SERVER_URL, self.path))
        self.index_of_current_screenshot += 1

        filename = '{} - {}.png'.format(self.user.code, self.index_of_current_screenshot)

        csv_row = {
            'filename': filename,
            'user': self.user._session_user.code,
            'app_label': self.subsession.app_label,
            'subsession_id': self.subsession.id,
            'page_name': ViewClass.__name__,
            # how do i get page index? do i even need it?
            #'page_index': 1,
        }

        self.browser.save_screenshot(os.path.join(self.screenshot_dir, filename))

    def _submit_core(self, ViewClass, data=None):
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
        if self.take_screenshots:
            self.screenshot(ViewClass)
        self.response = self.post(self.url, data, follow=True)
        self.assert_200()
        self.set_path()

    def submit(self, ViewClass, data=None):
        self._submit_with_valid_input(ViewClass, data)

    def _submit_with_valid_input(self, ViewClass, data=None):
        self._submit_core(ViewClass, data)

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
        self.response = self.get(self.url, follow=True)
        self.assert_200()
        self.set_path()

    def on_wait_page(self):
        return self.response.get(ptree.constants.wait_page_http_header) == ptree.constants.get_param_truth_value

    def page_redisplayed_with_errors(self):
        return self.response.get(ptree.constants.redisplay_with_errors_http_header) == ptree.constants.get_param_truth_value

    def set_path(self):
        try:
            self.url = self.response.redirect_chain[-1][0]
            self.path = urlsplit(self.url).path
        except IndexError:
            pass


class ParticipantBot(BaseClient):

    def __init__(self, user, **kwargs):
        self.user = user
        self.participant = user
        self.match = self.participant.match
        self.treatment = self.participant.treatment
        # we assume the experimenter has assigned everyone to a treatment
        assert self.match and self.treatment
        self.subsession = self.participant.subsession
        super(ParticipantBot, self).__init__(**kwargs)

class ExperimenterBot(BaseClient):

    def __init__(self, subsession, **kwargs):
        self.user = subsession._experimenter
        self.subsession = subsession
        super(ExperimenterBot, self).__init__(**kwargs)