#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import errno
from collections import OrderedDict

from django.conf import settings
from django.core.urlresolvers import reverse

from otree.models import Session
from otree.models_concrete import RoomToSession, ExpectedParticipant, ParticipantVisit
from otree.common_internal import add_params_to_url, make_hash


class Room(object):

    def __init__(self, config_dict):
        self.participant_label_file = config_dict.get('participant_label_file')
        self.name = config_dict['name']
        self.display_name = config_dict['display_name']
        self.use_secure_urls = config_dict.get('use_secure_urls', True)
        self.pin_code = config_dict.get('pin_code')

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
                        labels = [line.strip() for line in f if line.strip()]
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
            return set(ExpectedParticipant.objects.filter(room_name=self.name).values_list('participant_id', flat=True))
        raise Exception('no guestlist')

    def get_participant_links(self):
        participant_urls = []
        room_base_url = reverse('assign_visitor_to_room', args=(self.name,))
        if not self.use_secure_urls:
            participant_urls.append(room_base_url)

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


# If the server is restarted then forget all waiting participants and reload all participant labels
ParticipantVisit.objects.all().delete()
ExpectedParticipant.objects.all().delete()

ROOM_DICT = OrderedDict()
for room in getattr(settings, 'ROOMS', []):
    room = augment_room(room)
    room_object = Room(room)
    room_name = room_object.name
    for participant_label in room_object.load_participant_labels_from_file():
        ExpectedParticipant(room_name=room_name, participant_id=participant_label).save()
    ROOM_DICT[room_name] = room_object
