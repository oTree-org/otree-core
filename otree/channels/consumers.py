#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import django.db
import django.utils.timezone
import traceback
from datetime import timedelta

from channels import Group
from channels.generic.websockets import JsonWebsocketConsumer

import otree.session
from otree.models import Participant, Session
from otree.models_concrete import (
    CompletedGroupWaitPage, CompletedSubsessionWaitPage)
from otree.common_internal import (
    channels_wait_page_group_name, channels_create_session_group_name,
    channels_group_by_arrival_time_group_name, get_models_module
)
from otree.models_concrete import (
    FailedSessionCreation, ParticipantRoomVisit,
    FAILURE_MESSAGE_MAX_LENGTH, BrowserBotsLauncherSessionCode)
from otree.room import ROOM_DICT

logger = logging.getLogger(__name__)


class OTreeJsonWebsocketConsumer(JsonWebsocketConsumer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_attributes(**kwargs)

    def set_attributes(self, **kwargs):
        pass

    def group_name(self):
        raise NotImplementedError()

    def connection_groups(self, **kwargs):
        return [self.group_name()]

    def connect(self, message, **kwargs):
        self.message.reply_channel.send({"accept": True})
        self.post_connect()

    def post_connect(self):
        pass

class GroupByArrivalTime(OTreeJsonWebsocketConsumer):

    def set_attributes(self, params):
        session_pk, page_index, self.app_name, player_id = params.split(',')
        self.session_pk = int(session_pk)
        self.page_index = int(page_index)
        self.player_id = int(player_id)

    def group_name(self):
        return channels_group_by_arrival_time_group_name(
            self.session_pk, self.page_index)

    def post_connect(self):
        models_module = get_models_module(self.app_name)
        player = models_module.Player.objects.get(id=self.player_id)
        group_id_in_subsession = player.group.id_in_subsession

        ready = CompletedGroupWaitPage.objects.filter(
            page_index=self.page_index,
            id_in_subsession=int(group_id_in_subsession),
            session_id=self.session_pk,
            fully_completed=True).exists()
        if ready:
            self.send({'status': 'ready'})


class WaitPage(OTreeJsonWebsocketConsumer):

    def set_attributes(self, params):
        return {

        }
        session_pk, page_index, self.group_id_in_subsession = params.split(',')
        self.session_pk = int(session_pk)
        self.page_index = int(page_index)
        # don't convert group_id_in_subsession to int yet, it might be null

    def group_name(self):
        return channels_wait_page_group_name(
                self.session_pk, self.page_index, self.group_id_in_subsession)

    def post_connect(self):
        # in case message was sent before this web socket connects
        if self.group_id_in_subsession:
            ready = CompletedGroupWaitPage.objects.filter(
                page_index=self.page_index,
                id_in_subsession=int(self.group_id_in_subsession),
                session_id=self.session_pk,
                fully_completed=True).exists()
        else:  # subsession
            ready = CompletedSubsessionWaitPage.objects.filter(
                page_index=self.page_index,
                session_id=self.session_pk,
                fully_completed=True).exists()
        if ready:
            self.send({'status': 'ready'})


class AutoAdvance(OTreeJsonWebsocketConsumer):
    def set_attributes(self, params):
        self.participant_code, page_index = params.split(',')
        self.page_index = int(page_index)

    def group_name(self):
        return 'auto-advance-{}'.format(self.participant_code)

    def post_connect(self):
        # in case message was sent before this web socket connects
        result = Participant.objects.filter(
                code=self.participant_code).values_list(
            '_index_in_pages', flat=True)
        try:
            page_should_be_on = result[0]
        except IndexError:
            # doesn't get shown because not yet localized
            self.send({'error': 'Participant not found in database.'})
            return
        if page_should_be_on > self.page_index:
            self.send({'auto_advanced': True})


def create_session(message):
    group = Group(message['channels_group_name'])

    kwargs = message['kwargs']

    # because it's launched through web UI
    kwargs['honor_browser_bots_config'] = True
    try:
        otree.session.create_session(**kwargs)
    except Exception as e:

        # full error message is printed to console (though sometimes not?)
        error_message = 'Failed to create session: "{}"'.format(e)
        traceback_str = traceback.format_exc()
        group.send(
            {'text': json.dumps(
                {
                    'error': error_message,
                    'traceback': traceback_str,
                })}
        )
        FailedSessionCreation.objects.create(
            pre_create_id=kwargs['_pre_create_id'],
            message=error_message[:FAILURE_MESSAGE_MAX_LENGTH],
            traceback=traceback_str
        )
        raise

    group.send(
        {'text': json.dumps(
            {'status': 'ready'})}
    )

    if 'room_name' in kwargs:
        Group('room-participants-{}'.format(kwargs['room_name'])).send(
            {'text': json.dumps(
                {'status': 'session_ready'})}
        )


class WaitForSession(OTreeJsonWebsocketConsumer):
    def set_attributes(self, **kwargs):
        return self.kwargs

    def connection_groups(self, pre_create_id):
        group_name = channels_create_session_group_name(pre_create_id)
        return [group_name]

    def post_connect(self, pre_create_id):

        # in case message was sent before this web socket connects
        if Session.objects.filter(
                _pre_create_id=pre_create_id, ready=True).exists():
            self.group.send(
                {'text': json.dumps(
                    {'status': 'ready'})}
            )
        else:
            failure = FailedSessionCreation.objects.filter(
                pre_create_id=pre_create_id
            ).first()
            if failure:
                self.group.send(
                    {'text': json.dumps(
                        {'error': failure.message,
                         'traceback': failure.traceback})}
                )


class RoomAdmin(OTreeJsonWebsocketConsumer):
    def set_attributes(self, room):
        self.room = room

    def group_name(self):
        return 'room-admin-{}'.format(self.room)

    def post_connect(self):

        room_object = ROOM_DICT[self.room]

        now = django.utils.timezone.now()
        stale_threshold = now - timedelta(seconds=15)
        present_list = ParticipantRoomVisit.objects.filter(
            room_name=room_object.name,
            last_updated__gte=stale_threshold,
        ).values_list('participant_label', flat=True)

        # make it JSON serializable
        present_list = list(present_list)

        self.send({
            'status': 'load_participant_lists',
            'participants_present': present_list,
        })

        # prune very old visits -- don't want a resource leak
        # because sometimes not getting deleted on WebSocket disconnect
        very_stale_threshold = now - timedelta(minutes=10)
        ParticipantRoomVisit.objects.filter(
            room_name=room_object.name,
            last_updated__lt=very_stale_threshold,
        ).delete()


class RoomParticipant(OTreeJsonWebsocketConsumer):

    def set_attributes(self, params):
        self.room_name, self.participant_label, self.tab_unique_id = params.split(',')

    def post_connect(self):
        room_name = self.room_name
        participant_label = self.participant_label
        tab_unique_id = self.tab_unique_id


        if room_name in ROOM_DICT:
            room = ROOM_DICT[room_name]
        else:
            # doesn't get shown because not yet localized
            self.send({'error': 'Invalid room name "{}".'.format(room_name)})
            return
        if room.has_session():
            self.send({'status': 'session_ready'})
        else:
            try:
                ParticipantRoomVisit.objects.create(
                    participant_label=participant_label,
                    room_name=room_name,
                    tab_unique_id=tab_unique_id
                )
            except django.db.IntegrityError as exc:
                # possible that the tab connected twice
                # without disconnecting in between
                # because of WebSocket failure
                # tab_unique_id is unique=True,
                # so this will throw an integrity error.
                logger.info(
                    'ParticipantRoomVisit: not creating a new record because a '
                    'database integrity error was thrown. '
                    'The exception was: {}: {}'.format(type(exc), exc))
                pass
            self.group_send(
                'room-admin-{}'.format(room_name),
                {
                    'status': 'add_participant',
                    'participant': participant_label
                }
            )


    def disconnect(self, message, **kwargs):
        room_name = self.room_name
        participant_label = self.participant_label
        tab_unique_id = self.tab_unique_id

        if room_name in ROOM_DICT:
            room = ROOM_DICT[room_name]
        else:
            # doesn't get shown because not yet localized
            self.send({'error': 'Invalid room name "{}".'.format(room_name)})
            return

        # should use filter instead of get,
        # because if the DB is recreated,
        # the record could already be deleted
        ParticipantRoomVisit.objects.filter(
            participant_label=participant_label,
            room_name=room_name,
            tab_unique_id=tab_unique_id).delete()

        if room.has_participant_labels():
            if not ParticipantRoomVisit.objects.filter(
                participant_label=participant_label,
                room_name=room_name
            ).exists():
                # it's ok if there is a race condition --
                # in JS removing a participant is idempotent
                self.group_send(
                    'room-admin-{}'.format(room_name),
                    {
                        'status': 'remove_participant',
                        'participant': participant_label
                    }
                )
        else:
            self.group_send(
                'room-admin-{}'.format(room_name),
                {
                    'status': 'remove_participant',
                }
            )


class BrowserBotsClient(OTreeJsonWebsocketConsumer):

    def group_name
    def connection_groups(self, **kwargs):
        group_name = 'browser-bots-client-{}'.format(self.kwargs['session_code'])
        return [group_name]


class BrowserBot(OTreeJsonWebsocketConsumer):
    def connection_groups(self, **kwargs):
        return ['browser_bot_wait']

    def post_connect(self):
        launcher_session_info = BrowserBotsLauncherSessionCode.objects.first()
        if launcher_session_info:
            self.send({'status': 'session_ready'})
