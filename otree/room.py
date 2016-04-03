from collections import OrderedDict
from django.conf import settings
from otree.models import Session
from otree.models_concrete import RoomSession
from django.core.urlresolvers import reverse
from otree.common_internal import add_params_to_url

class Room(object):

    def __init__(self, name, display_name, participant_label_file=None):
        self.participant_label_file = participant_label_file
        self.name = name
        self.display_name = display_name

    def has_session(self):
        return self.session is not None

    @property
    def session(self):
        try:
            session_pk = RoomSession.objects.get(room_name=self.name).session_pk
            return Session.objects.get(pk=session_pk)
        except (RoomSession.DoesNotExist, Session.DoesNotExist):
            return None

    @session.setter
    def session(self, session):
        if session is None:
            RoomSession.objects.filter(room_name=self.name).delete()
        else:
            room_session, created = RoomSession.objects.get_or_create(room_name=self.name)
            room_session.session_pk = session.pk
            room_session.save()

    def has_participant_labels(self):
        return bool(self.participant_label_file)

    def get_participant_labels(self):
        if self.has_participant_labels():
            with open(self.participant_label_file) as f:
                labels = [line.strip() for line in f if line.strip()]
                return labels
        raise Exception('no guestlist')

    def get_participant_links(self):
        participant_urls = []
        room_base_url = add_params_to_url(reverse('assign_visitor_to_room'), {'room': self.name})
        if self.has_participant_labels():
            for label in self.get_participant_labels():
                participant_url = add_params_to_url(
                    room_base_url,
                    {
                        'participant_label': label
                    }
                )
                participant_urls.append(participant_url)
        else:
            participant_urls = [room_base_url]

        return participant_urls

    def url(self):
        return reverse('room_without_session', args=(self.name,))

    def url_close(self):
        return reverse('close_room', args=(self.name,))

ROOM_DICT = OrderedDict()
for room in settings.ROOMS:
    ROOM_DICT[room['name']] = Room(room['name'], room['display_name'], room.get('participant_label_file'))
