from collections import OrderedDict
from django.conf import settings
from otree.models import Session
from otree.models_concrete import RoomSession

class Room(object):

    def __init__(self, name, participant_label_file=None):
        self.participant_label_file = participant_label_file
        self.name = name

    @property
    def session(self):
        try:
            return RoomSession.objects.get(room=self.name)
        except RoomSession.DoesNotExist:
            return None

    def has_participant_labels(self):
        return bool(self.participant_label_file)

    def get_participant_labels(self):
        if self.has_participant_labels():
            with open(self.participant_label_file) as f:
                labels = [line.strip() for line in f if line.strip()]
                return labels
        raise Exception('no guestlist')

ROOM_DICT = OrderedDict()
for room in settings.ROOMS:
    ROOM_DICT[room['name']] = Room(room['name'], room.get('participant_label_file'))

