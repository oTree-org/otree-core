from pathlib import Path
from otree.models_concrete import RoomToSession
from otree.common import add_params_to_url, make_hash, validate_alphanumeric
from otree import settings
from otree.database import db, NoResultFound
from collections import defaultdict
from typing import Dict


class BaseRoom:
    use_secure_urls = False

    def __init__(
        self, name, display_name,
    ):
        self.name = validate_alphanumeric(
            name, identifier_description='settings.ROOMS room name'
        )
        self.display_name = display_name

    def has_session(self):
        return self.get_session() is not None

    def presence_add(self):
        raise NotImplementedError

    def presence_remove(self):
        raise NotImplementedError

    def get_session(self):
        try:
            return RoomToSession.objects_get(room_name=self.name).session
        except NoResultFound:
            return None

    def set_session(self, session):
        RoomToSession.objects_filter(room_name=self.name).delete()
        if session:
            RoomToSession.objects_create(room_name=self.name, session=session)

    def get_room_wide_url(self, request):
        return request.url_for('AssignVisitorToRoom', room_name=self.name)

    def get_participant_urls(self, request):
        return []

    def rest_api_dict(self, request) -> dict:
        session = self.get_session()
        if session:
            session_code = session.code
        else:
            session_code = None
        return dict(
            # better to include session_code key even if it's blank,
            # so that people can see the schema and know that session code
            # will be there if they create a session
            session_code=session_code,
            name=self.name,
            url=self.get_room_wide_url(request),
        )


class NoLabelRoom(BaseRoom):
    has_participant_labels = False
    present_count = 0

    def presence_add(self, label):
        self.present_count += 1

    def presence_remove(self, label):
        self.present_count -= 1


class LabelRoom(BaseRoom):
    has_participant_labels = True
    present_list: list

    def __init__(
        self, name, display_name, participant_label_file, use_secure_urls=False,
    ):
        super().__init__(name, display_name)
        self.participant_label_file = participant_label_file
        self.use_secure_urls = use_secure_urls
        self.present_list = []

    def presence_add(self, label):
        self.present_list.append(label)

    def presence_remove(self, label):
        self.present_list.remove(label)

    def get_participant_urls(self, request):
        participant_urls = []
        room_base_url = request.url_for('AssignVisitorToRoom', room_name=self.name)

        for label in self.get_participant_labels():
            params = {'participant_label': label}
            if self.use_secure_urls:
                params['hash'] = make_hash(label)
            participant_url = add_params_to_url(room_base_url, params)
            participant_urls.append(participant_url)

        return participant_urls

    def get_participant_labels(self):
        labels = Path(self.participant_label_file).read_text(encoding='utf8').split()
        for label in labels:
            validate_alphanumeric(label, identifier_description='participant label')
        # eliminate duplicates
        return list(dict.fromkeys(labels))


def get_room_dict() -> Dict[str, BaseRoom]:
    ROOMS = getattr(settings, 'ROOMS', [])
    ROOM_DICT = {}
    for room in ROOMS:
        # extra layer in case ROOM_DEFAULTS has the same key
        # as a room
        if room.get('participant_label_file'):
            room_object = LabelRoom(**room)
        else:
            if room.get('use_secure_urls'):
                msg = (
                    'Room "{}": you must either set participant_label_file, '
                    'or set use_secure_urls=False'.format(room['name'])
                )
                raise ValueError(msg)
            room_object = NoLabelRoom(**room)
        ROOM_DICT[room_object.name] = room_object
    return ROOM_DICT


ROOM_DICT = get_room_dict()
