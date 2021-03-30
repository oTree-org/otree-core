import json
from logging import getLogger
import time
from time import sleep
from urllib import request, parse
from urllib.error import URLError
from urllib.parse import urljoin
from otree.database import db, session_scope
import otree.constants
from otree.models_concrete import TaskQueueMessage

print_function = print


logger = getLogger(__name__)


def post(url, data: dict):
    '''
    make the request over the network rather than in-process,
    to avoid race conditions. everything must be handled by the main
    server instance.
    '''
    data = parse.urlencode(data).encode()
    req = request.Request(url, data=data)  # this will make the method "POST"
    resp = request.urlopen(req)


def get(url):
    try:
        request.urlopen(url)
    # some users were reporting URLError but not clear what URL it was
    except URLError as exc:
        raise Exception(f'Error occurred when opening {url}: {repr(exc)}') from None


class Worker:
    def __init__(self, port):
        self.base_url = f'http://127.0.0.1:{port}'
        # delete all old stuff

        TaskQueueMessage.objects_filter(
            TaskQueueMessage.epoch_time < time.time() - 60
        ).delete()

    def listen(self):
        print_function('timeoutworker is listening for messages through DB')

        while True:
            # without the session_scope, resetdb doesn't work because it seems to require
            # all connections to be closed, even in other processes.
            with session_scope():
                for task in TaskQueueMessage.objects_filter(
                    TaskQueueMessage.epoch_time <= time.time()
                ).order_by('epoch_time'):
                    try:
                        getattr(self, task.method)(**task.kwargs())
                    except Exception as exc:
                        # don't raise, because then this would crash.
                        # logger.exception() will record the full traceback
                        logger.exception(repr(exc))
                    db.delete(task)
            sleep(3)

    def submit_expired_url(self, participant_code, page_index):
        from otree.models.participant import Participant

        # if the participant exists in the DB,
        # and they did not advance past the page yet

        # To reduce redundant server traffic, it's OK not to advance the page if the user already got to the next page
        # themselves, or via "advance slowest participants".
        # however, we must make sure that the user succeeded in loading the next page fully.
        # if the user made this page's POST but closed their browser before
        # the redirect to the next page's GET, then if the next page has a timeout,
        # it will not get scheduled, and then the auto-timeout chain would be broken.
        # so, instead of filtering by _index_in_pages (which is set in POST),
        # we filter by _current_form_page_url (which is set in GET,
        # AFTER the next page's timeout is scheduled.)

        pp = Participant.objects_filter(
            code=participant_code, _index_in_pages=page_index
        ).first()
        if pp:
            path = pp._url_i_should_be_on()
            logger.info(f'Auto-submitting timed out page: {path}')
            post(
                urljoin(self.base_url, path),
                data={otree.constants.timeout_happened: True},
            )

    def ensure_pages_visited(self, participant_pks, page_index):
        """This is necessary when a wait page is followed by a timeout page.
        We can't guarantee the user's browser will properly continue to poll
        the wait page and get redirected, so after a grace period we load the page
        automatically, to kick off the expiration timer of the timeout page.
        """

        from otree.models.participant import Participant

        # we used to filter by _index_in_pages, but that is not reliable,
        # because of the race condition described above.
        unvisited_participants = Participant.objects_filter(
            Participant.id.in_(participant_pks),
            # the +1 is just a buffer for any edge cases
            # (as we saw with advance_slowest)
            Participant._index_in_pages <= page_index + 1,
        )
        for pp in unvisited_participants:

            # if the wait page is the first page,
            # then _current_form_page_url could be null.
            # in this case, use the start_url() instead,
            # because that will redirect to the current wait page.
            # (alternatively we could define _current_page_url or
            # current_wait_page_url)
            path = pp._url_i_should_be_on()
            logger.info(f'Auto-submitting timed out page: {path}')

            get(urljoin(self.base_url, path))


def _db_enqueue(method, delay, kwargs):
    TaskQueueMessage.objects_create(
        method=method,
        epoch_time=delay + round(time.time()),
        kwargs_json=json.dumps(kwargs),
    )


def ensure_pages_visited(delay, **kwargs):
    _db_enqueue(method='ensure_pages_visited', delay=delay, kwargs=kwargs)


def submit_expired_url(delay, **kwargs):
    _db_enqueue(method='submit_expired_url', delay=delay, kwargs=kwargs)
