from collections import OrderedDict
from django.conf import settings

ROOM_DICT = OrderedDict()
for room in settings.ROOMS:
    ROOM_DICT[room['name']] = room

for room_session in RoomSession.objects.all():
    ROOM_DICT[room_session.room_name]['session']

SESSION_CONFIGS_DICT = OrderedDict()
for config in settings.SESSION_CONFIGS:
    SESSION_CONFIGS_DICT[config['name']] = augment_session_config(config)

def get_participant_labels(room_name):
    room = ROOM_DICT[room_name]
    # TODO: label file should be optional?
    label_file_name = room['participant_label_file']
    with open(label_file_name) as f:
        labels = [line.strip() for line in f if line.strip()]
        return labels

def

for room in ROOMS:

