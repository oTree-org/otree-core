from django.core.urlresolvers import reverse
from otree.session import create_session
from tests import TestCase
import splinter
from django.conf import settings
from otree.models.participant import Participant

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
