#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import errno
import re
from collections import OrderedDict

from django.conf import settings
from django.core.urlresolvers import reverse

from otree.models import Session
from otree.models_concrete import RoomToSession, ExpectedRoomParticipant
from otree.common_internal import add_params_to_url, make_hash
from django.db import transaction


def validate_label(label):
    if re.match(r'^[a-zA-Z0-9_]+$', label):
        return label
    raise ValueError(
        'Error in participant label "{}": participant labels must contain '
        'only the following characters: a-z, A-Z, 0-9, _.'.format(label)
    )


class Room(object):

    def __init__(self, config_dict):
        self.participant_label_file = config_dict.get('participant_label_file')
        self.name = config_dict['name']
        self.display_name = config_dict['display_name']
        # secure URLs are complicated, don't use them by default
        self.use_secure_urls = config_dict.get('use_secure_urls', False)
        self.pin_code = config_dict.get('pin_code')
        self._participant_labels_loaded = False
        if self.use_secure_urls and not self.participant_label_file:
            raise ValueError(
                'Room "{}": you must either set "participant_label_file", '
                'or set "use_secure_urls": False'.format(self.name)
            )

    def has_session(self):
        return self.session is not None

    @property
    def session(self):
        try:
            return RoomToSession.objects.select_related('session').get(
                room_name=self.name).session
        except RoomToSession.DoesNotExist:
            return None

    @session.setter
    def session(self, session):
        RoomToSession.objects.filter(room_name=self.name).delete()
        if session:
            RoomToSession.objects.create(
                room_name=self.name,
                session=session
            )

    def has_participant_labels(self):
        return bool(self.participant_label_file)

    def load_participant_labels_to_db(self):
        if self.has_participant_labels():
            encodings = ['ascii', 'utf-8', 'utf-16']
            for e in encodings:
                try:
                    plabel_path = self.participant_label_file
                    with codecs.open(plabel_path, "r", encoding=e) as f:
                        labels = [
                            validate_label(line.strip()) for line in f if line.strip()
                        ]
                except UnicodeDecodeError:
                    continue
                except OSError as err:
                    # this code is equivalent to "except FileNotFoundError:"
                    # but works in py2 and py3
                    if err.errno == errno.ENOENT:
                        msg = (
                            'The room "{}" references nonexistent '
                            'participant_label_file "{}". '
                            'Check your settings.py.')
                        raise IOError(
                            msg.format(self.name, self.participant_label_file))
                    raise err
                else:
                    with transaction.atomic():
                        # use select_for_update to prevent race conditions
                        ExpectedRoomParticipant.objects.select_for_update()
                        ExpectedRoomParticipant.objects.filter(
                            room_name=self.name).delete()
                        ExpectedRoomParticipant.objects.bulk_create(
                            ExpectedRoomParticipant(
                                room_name=self.name,
                                participant_label=participant_label
                            ) for participant_label in labels
                        )
                    self._participant_labels_loaded = True
                    return
            raise Exception('Failed to decode guest list.')
        raise Exception('no guestlist')

    def get_participant_labels(self):
        if self.has_participant_labels():
            if not self._participant_labels_loaded:
                self.load_participant_labels_to_db()
            return ExpectedRoomParticipant.objects.filter(
                    room_name=self.name
                ).order_by('id').values_list('participant_label', flat=True)
        raise Exception('no guestlist')

    def num_participant_labels(self):
        if not self._participant_labels_loaded:
            self.load_participant_labels_to_db()
        return ExpectedRoomParticipant.objects.filter(
            room_name=self.name
        ).count()

    def get_room_wide_url(self, request):
        url = reverse('assign_visitor_to_room', args=(self.name,))
        return request.build_absolute_uri(url)

    def get_participant_urls(self, request):
        participant_urls = []
        room_base_url = reverse('assign_visitor_to_room', args=(self.name,))
        room_base_url = request.build_absolute_uri(room_base_url)

        if self.has_participant_labels():
            for label in self.get_participant_labels():
                params = {'participant_label': label}
                if self.use_secure_urls:
                    params['hash'] = make_hash(label)
                participant_url = add_params_to_url(room_base_url, params)
                participant_urls.append(participant_url)

        return participant_urls

    def has_pin_code(self):
        return bool(self.pin_code)

    def get_pin_code(self):
        return self.pin_code

    def url(self):
        return reverse('room_without_session', args=(self.name,))

    def url_close(self):
        return reverse('close_room', args=(self.name,))


def augment_room(room):
    new_room = {'doc': ''}
    new_room.update(getattr(settings, 'ROOM_DEFAULTS', {}))
    new_room.update(room)
    return new_room

def get_room_dict():
    ROOM_DICT = OrderedDict()
    for room in getattr(settings, 'ROOMS', []):
        room = augment_room(room)
        room_object = Room(room)
        room_name = room_object.name
        ROOM_DICT[room_object.name] = room_object
    return ROOM_DICT

ROOM_DICT = get_room_dict()

