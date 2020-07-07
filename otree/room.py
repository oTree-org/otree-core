from pathlib import Path
from otree.models_concrete import RoomToSession
from otree.common import add_params_to_url, make_hash, validate_alphanumeric
from django.conf import settings
from django.urls import reverse
from django.db import transaction


class Room:
    def __init__(
        self, name, display_name, use_secure_urls=False, participant_label_file=None
    ):
        self.name = validate_alphanumeric(
            name, identifier_description='settings.ROOMS room name'
        )
        if use_secure_urls and not participant_label_file:
            msg = (
                'Room "{}": you must either set "participant_label_file", '
                'or set "use_secure_urls": False'.format(name)
            )
            raise ValueError(msg)
        self.participant_label_file = participant_label_file
        self.display_name = display_name
        # secure URLs are complicated, don't use them by default
        self.use_secure_urls = use_secure_urls

    def has_session(self):
        return self.get_session() is not None

    def get_session(self):
        try:
            return (
                RoomToSession.objects.select_related('session')
                .get(room_name=self.name)
                .session
            )
        except RoomToSession.DoesNotExist:
            return None

    def set_session(self, session):
        with transaction.atomic():
            RoomToSession.objects.filter(room_name=self.name).delete()
            if session:
                RoomToSession.objects.create(room_name=self.name, session=session)

    def has_participant_labels(self):
        return bool(self.participant_label_file)

    def get_participant_labels(self):
        lines = (
            Path(self.participant_label_file).read_text(encoding='utf8').splitlines()
        )
        labels = []
        for line in lines:
            label = line.strip()
            if label:
                validate_alphanumeric(label, identifier_description='participant label')
                labels.append(label)
        # eliminate duplicates
        return list(dict.fromkeys(labels))

    def get_room_wide_url(self, request):
        url = reverse('AssignVisitorToRoom', args=(self.name,))
        return request.build_absolute_uri(url)

    def get_participant_urls(self, request):
        participant_urls = []
        room_base_url = reverse('AssignVisitorToRoom', args=(self.name,))
        room_base_url = request.build_absolute_uri(room_base_url)

        if self.has_participant_labels():
            for label in self.get_participant_labels():
                params = {'participant_label': label}
                if self.use_secure_urls:
                    params['hash'] = make_hash(label)
                participant_url = add_params_to_url(room_base_url, params)
                participant_urls.append(participant_url)

        return participant_urls


def get_room_dict():
    ROOM_DEFAULTS = getattr(settings, 'ROOM_DEFAULTS', {})
    ROOMS = getattr(settings, 'ROOMS', [])
    ROOM_DICT = {}
    for room in ROOMS:
        # extra layer in case ROOM_DEFAULTS has the same key
        # as a room
        room_object = Room(**dict(ROOM_DEFAULTS, **room))
        ROOM_DICT[room_object.name] = room_object
    return ROOM_DICT


ROOM_DICT = get_room_dict()
