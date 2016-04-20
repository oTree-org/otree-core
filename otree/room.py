from collections import OrderedDict
from django.conf import settings
from otree.models import Session
from otree.models_concrete import RoomSession
from django.core.urlresolvers import reverse
from otree.common_internal import add_params_to_url, make_hash
import codecs

class Room(object):

    def __init__(self, room_config_dict):
        self.participant_label_file = room_config_dict.get('participant_label_file')
        self.name = room_config_dict['name']
        self.display_name = room_config_dict['display_name']
        self.use_secure_urls = room_config_dict['use_secure_urls']

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
            encodings = ['utf-8', 'utf-16', 'ascii']
            for e in encodings:
                try:
                    with codecs.open(self.participant_label_file, "r", encoding=e) as f:
                        labels = [line.strip() for line in f if line.strip()]
                        return labels
                except UnicodeDecodeError:
                    continue

            raise Exception('Failed to decode guest list.')
        raise Exception('no guestlist')

    def get_participant_links(self):
        participant_urls = []
        room_base_url = add_params_to_url(reverse('assign_visitor_to_room'), {'room': self.name})
        if self.has_participant_labels():
            for label in self.get_participant_labels():
                params = {'participant_label': label}
                if self.use_secure_urls:
                    params['hash'] = make_hash(label)
                participant_url = add_params_to_url(room_base_url, params)
                participant_urls.append(participant_url)
        else:
            participant_urls = [room_base_url]

        return participant_urls

    def url(self):
        return reverse('room_without_session', args=(self.name,))

    def url_close(self):
        return reverse('close_room', args=(self.name,))

def augment_room(room):
    new_room = {'doc': ''}
    new_room.update(settings.ROOM_DEFAULTS)
    new_room.update(room)
    return new_room

ROOM_DICT = OrderedDict()
for room in getattr(settings, 'ROOMS', []):
    room = augment_room(room)
    ROOM_DICT[room['name']] = Room(room)
