#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import errno
from collections import OrderedDict

from django.conf import settings
from django.core.urlresolvers import reverse

from otree.models import Session
from otree.models_concrete import RoomToSession, ExpectedRoomParticipant, ParticipantRoomVisit
from otree.common_internal import add_params_to_url, make_hash
from django.db import transaction

ILLEGAL_PARTICIPANT_LABEL_CHARS = {'"', '<', '>', '&'}

def validate_label(label):
    # participant label is used in the id of their span,
    # so it shouldn't contain any chars that are escaped
    # by HTML, like &quot; &gt; etc.
    for char in label:
        if char in ILLEGAL_PARTICIPANT_LABEL_CHARS:
            raise ValueError(
                'Participant label "{}" contains one of the following '
                'disallowed characters: {}'.format(
                    label,
                    ' '.join(ILLEGAL_PARTICIPANT_LABEL_CHARS)
                )
            )
    return label


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
                'or set "use_secure_urls": False'
            )

    def has_session(self):
        return self.session is not None

    @property
    def session(self):
        session_pk_qs = RoomToSession.objects.filter(
            room_name=self.name).values('session_pk')
        return Session.objects.filter(pk__in=session_pk_qs).first()

    @session.setter
    def session(self, session):
        if session is None:
            RoomToSession.objects.filter(room_name=self.name).delete()
        else:
            RoomToSession.objects.get_or_create(
                room_name=self.name, defaults={'session_pk': session.pk})

    def has_participant_labels(self):
        return bool(self.participant_label_file)

    def load_participant_labels_from_file(self):
        if self.has_participant_labels():
            encodings = ['utf-8', 'utf-16', 'ascii']
            for e in encodings:
                try:
                    plabel_path = self.participant_label_file
                    with codecs.open(plabel_path, "r", encoding=e) as f:
                        labels = [
                            validate_label(line.strip()) for line in f if line.strip()
                        ]
                        return labels
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
            raise Exception('Failed to decode guest list.')
        raise Exception('no guestlist')

    def get_participant_labels(self):
        if self.has_participant_labels():
            if not self._participant_labels_loaded:
                with transaction.atomic():
                    # use select_for_update to prevent race conditions
                    ExpectedRoomParticipant.objects.select_for_update()
                    ExpectedRoomParticipant.objects.all().delete()
                    ExpectedRoomParticipant.objects.bulk_create(
                        ExpectedRoomParticipant(
                            room_name=self.name,
                            participant_label=participant_label
                        ) for participant_label in self.load_participant_labels_from_file()
                    )
                    self._participant_labels_loaded = True
            return ExpectedRoomParticipant.objects.filter(
                    room_name=self.name
                ).order_by('id').values_list('participant_label', flat=True)
        raise Exception('no guestlist')

    def num_participant_labels(self):
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

