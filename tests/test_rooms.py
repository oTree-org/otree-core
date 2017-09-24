from django.core.urlresolvers import reverse
from otree.session import create_session
from .utils import TestCase
import splinter
from django.conf import settings
from otree.models.participant import Participant
import otree.channels.utils as channel_utils
from channels.tests import ChannelTestCase, HttpClient
from unittest.mock import patch
import django.test
import json

URL_ADMIN_LABELS = reverse('RoomWithoutSession', args=[settings.ROOM_WITH_LABELS_NAME])
URL_ADMIN_NO_LABELS = reverse('RoomWithoutSession', args=[settings.ROOM_WITHOUT_LABELS_NAME])
URL_PARTICIPANT_LABELS = reverse('AssignVisitorToRoom', args=[settings.ROOM_WITH_LABELS_NAME])
URL_PARTICIPANT_NO_LABELS = reverse('AssignVisitorToRoom', args=[settings.ROOM_WITHOUT_LABELS_NAME])

LABEL_REAL = 'JohnSmith'
LABEL_FAKE = 'NotInParticipantLabelsFile'


def add_label(base_url, label):
    return base_url + '?participant_label={}'.format(label)


class RoomTestCase(TestCase):

    def setUp(self):
        self.browser = splinter.Browser('django') # type: splinter.Browser

    def get(self, url):
        self.browser.visit(url)


class TestRoomWithoutSession(RoomTestCase):

    def test_open_admin_links(self):
        urls = [
            reverse('Rooms'),
            URL_ADMIN_LABELS,
            URL_ADMIN_NO_LABELS,
        ]

        for url in urls:
            self.get(url)

    def test_open_participant_links(self):

        WAITING_STR = 'Waiting for your session to begin'

        br = self.browser

        self.get(URL_PARTICIPANT_LABELS)
        self.assertIn('Please enter your participant label', br.html)

        self.get(
            add_label(URL_PARTICIPANT_LABELS, LABEL_REAL)
        )

        self.assertIn(WAITING_STR, br.html)

        self.get(add_label(URL_PARTICIPANT_LABELS, LABEL_FAKE))
        self.assertEqual(br.status_code, 404)


        self.get(URL_PARTICIPANT_NO_LABELS)
        self.assertIn(WAITING_STR, br.html)

        self.get(add_label(URL_PARTICIPANT_NO_LABELS, LABEL_REAL))
        self.assertIn(WAITING_STR, br.html)

    def test_ping(self):
        pass


class TestRoomWithSession(RoomTestCase):
    def _visited_count(self, session):
        return session.participant_set.filter(visited=True).count()

    def visited_count_labels(self):
        return self._visited_count(self.session_with_labels)

    def visited_count_no_labels(self):
        return self._visited_count(self.session_without_labels)

    def setUp(self):
        super().setUp()
        self.session_with_labels = create_session(
            'simple',
            # make it 6 so that we can test if the participant is reassigned
            # if they open their start link again (1/6 chance)
            num_participants=6,
            room_name=settings.ROOM_WITH_LABELS_NAME,
        )

        self.session_without_labels = create_session(
            'simple',
            num_participants=2,
            room_name=settings.ROOM_WITHOUT_LABELS_NAME,
        )

    def tearDown(self):
        for url in [URL_ADMIN_LABELS, URL_ADMIN_NO_LABELS]:
            self.get(url)
            button = self.browser.find_by_id('close-room')
            button.click()

        self.get(URL_ADMIN_LABELS)
        self.assertIn('room_without_session', self.browser.url)

    def test_open_admin_links(self):
        self.get(URL_ADMIN_LABELS)
        self.assertIn('room_with_session', self.browser.url)

    def test_without_label(self):

        self.get(URL_PARTICIPANT_NO_LABELS)
        self.get(URL_PARTICIPANT_NO_LABELS)

        # should use a cookie, so it remembers the participant
        self.assertEqual(self.visited_count_no_labels(), 1)

        self.get(add_label(URL_PARTICIPANT_NO_LABELS, LABEL_REAL))
        self.assertEqual(self.visited_count_no_labels(), 2)

    def test_with_label(self):
        br = self.browser

        self.get(URL_PARTICIPANT_LABELS)
        self.assertIn('Please enter your participant label', br.html)

        self.get(add_label(URL_PARTICIPANT_LABELS, LABEL_FAKE))
        self.assertEqual(br.status_code, 404)
        self.assertEqual(self.visited_count_labels(), 0)

        # make sure reopening the same link assigns you to same participant
        for i in range(2):
            self.get(add_label(URL_PARTICIPANT_LABELS, LABEL_REAL))

        visited_participants = Participant.objects.filter(visited=True)
        self.assertEqual(len(visited_participants), 1)

        participant = visited_participants[0]

        self.assertEqual(participant.label, LABEL_REAL)

    def test_delete_session_in_room(self):
        pass

    def test_session_start_links_room(self):
        pass

class RoomClient(HttpClient):
    def __init__(self, path):
        self.path = path
        super().__init__()

    def connect(self):
        self.send_and_consume('websocket.connect', {'path': self.path})

    def disconnect(self):
        self.send_and_consume('websocket.disconnect', {'path': self.path})


class PresenceWithLabelsTests(ChannelTestCase):

    def setUp(self):
        self.participant_label = LABEL_REAL
        room_name = settings.ROOM_WITH_LABELS_NAME
        self.room_name = room_name
        self.tab_unique_id = '12123123'
        self.path = channel_utils.room_participant_path(
            room_name, self.participant_label, self.tab_unique_id)
        self.admin_path = channel_utils.room_admin_path(room_name)
        self.participant_client = RoomClient(self.path)
        self.admin_client = RoomClient(self.admin_path)

    @patch('time.time')
    def test_stale_visits(self, patched_time):

        patched_time.return_value = 0

        # participant connects
        self.participant_client.connect()

        # time passes, participant does not disconnect but becomes stale
        patched_time.return_value = 30

        # admin requests StaleRoomVisits, should include that participant
        client = django.test.Client()
        heartbeat_url = reverse('ParticipantRoomHeartbeat', args=[self.tab_unique_id])
        stale_room_visits_url = reverse('StaleRoomVisits', args=[self.room_name])

        resp = client.get(stale_room_visits_url)
        self.assertJSONEqual(
            resp.content.decode('utf8'),
            {'participant_labels': [self.participant_label]}
        )

        # participant heartbeat occurs
        client.get(heartbeat_url)

        resp = client.get(stale_room_visits_url)
        self.assertJSONEqual(
            resp.content.decode('utf8'),
            {'participant_labels': []}
        )


    def test_participant_before_admin(self):

        participant_client = self.participant_client
        admin_client = self.admin_client

        participant_client.connect()

        admin_client.connect()

        # check that DB record created properly
        self.assertEqual(
            admin_client.receive(),
            {
                'status': 'load_participant_lists',
                'participants_present': [self.participant_label],
            }
        )

    def test_admin_before_participant(self):
        participant_client = self.participant_client
        admin_client = self.admin_client

        admin_client.connect()
        self.assertEqual(
            admin_client.receive(),
            {
                'status': 'load_participant_lists',
                'participants_present': [],
            }
        )

        participant_client.connect()

        self.assertEqual(
            admin_client.receive(),
            {'status': 'add_participant', 'participant': self.participant_label}
        )

    def test_participant_disconnect(self):
        participant_client = self.participant_client
        admin_client = self.admin_client

        participant_client.connect()
        admin_client.connect()
        admin_client.receive()

        participant_client.disconnect()
        self.assertEqual(
            admin_client.receive(),
            {'status': 'remove_participant', 'participant': self.participant_label}
        )

    def test_with_session(self):
        participant_client = self.participant_client
        create_session(
            'simple',
            num_participants=2,
            room_name=settings.ROOM_WITH_LABELS_NAME,
        )
        participant_client.connect()
        self.assertEqual(
            participant_client.receive(),
            {'status': 'session_ready'}
        )


class PresenceWithoutLabelsTests(ChannelTestCase):

    def setUp(self):

        room_name = settings.ROOM_WITHOUT_LABELS_NAME
        self.room_name = room_name
        self.tab_unique_id = '12123123'
        self.path = channel_utils.room_participant_path(
            room_name=room_name,
            participant_label='',
            tab_unique_id=self.tab_unique_id)
        self.admin_path = channel_utils.room_admin_path(room_name)
        self.participant_client = RoomClient(self.path)
        self.admin_client = RoomClient(self.admin_path)

    @patch('time.time')
    def test_stale_visits(self, patched_time):

        patched_time.return_value = 0

        # participant connects
        self.participant_client.connect()

        # time passes, participant does not disconnect but becomes stale
        patched_time.return_value = 30

        # admin requests StaleRoomVisits, should include that participant
        client = django.test.Client()
        heartbeat_url = reverse('ParticipantRoomHeartbeat', args=[self.tab_unique_id])
        participant_count_url = reverse('ActiveRoomParticipantsCount', args=[self.room_name])

        resp = client.get(participant_count_url)
        self.assertJSONEqual(
            resp.content.decode('utf8'),
            {'count': 0}
        )

        # participant heartbeat occurs
        client.get(heartbeat_url)

        resp = client.get(participant_count_url)
        self.assertJSONEqual(
            resp.content.decode('utf8'),
            {'count': 1}
        )


    def test_participant_before_admin(self):

        participant_client = self.participant_client
        admin_client = self.admin_client

        participant_client.connect()
        admin_client.connect()

        # check that DB record created properly
        self.assertEqual(
            admin_client.receive(),
            {
                'status': 'load_participant_lists',
                'participants_present': [''],
            }
        )

    def test_admin_before_participant(self):
        participant_client = self.participant_client
        admin_client = self.admin_client

        admin_client.connect()
        self.assertEqual(
            admin_client.receive(),
            {
                'status': 'load_participant_lists',
                'participants_present': [],
            }
        )

        participant_client.connect()

        self.assertEqual(
            admin_client.receive(),
            {'status': 'add_participant', 'participant': ''}
        )

    def test_participant_disconnect(self):
        participant_client = self.participant_client
        admin_client = self.admin_client

        participant_client.connect()
        admin_client.connect()
        admin_client.receive()

        participant_client.disconnect()
        self.assertEqual(
            admin_client.receive(),
            {'status': 'remove_participant'}
        )