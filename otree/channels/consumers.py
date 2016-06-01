#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json

from channels import Group

from otree.models import Participant
from otree.models_concrete import (
    CompletedGroupWaitPage, CompletedSubsessionWaitPage)
from otree.common_internal import (
    channels_wait_page_group_name, channels_create_session_group_name)

import otree.session
from otree.models import Session
from otree.models_concrete import (
    FailedSessionCreation,
    ParticipantVisit,
    FAILURE_MESSAGE_MAX_LENGTH,
)
from otree.views.abstract import lock_on_this_code_path
from otree.room import ROOM_DICT


def connect_wait_page(message, params):
    session_pk, page_index, model_name, model_pk = params.split(',')
    session_pk = int(session_pk)
    page_index = int(page_index)
    model_pk = int(model_pk)

    group_name = channels_wait_page_group_name(
        session_pk, page_index, model_name, model_pk
    )
    group = Group(group_name)
    group.add(message.reply_channel)

    # in case message was sent before this web socket connects
    if model_name == 'group':
        ready = CompletedGroupWaitPage.objects.filter(
            page_index=page_index,
            group_pk=model_pk,
            session_pk=session_pk,
            after_all_players_arrive_run=True).exists()
    else:  # subsession
        ready = CompletedSubsessionWaitPage.objects.filter(
            page_index=page_index,
            session_pk=session_pk,
            after_all_players_arrive_run=True).exists()
    if ready:
        message.reply_channel.send(
            {'text': json.dumps(
                {'status': 'ready'})})


def disconnect_wait_page(message, params):
    app_label, page_index, model_name, model_pk = params.split(',')
    page_index = int(page_index)
    model_pk = int(model_pk)

    group_name = channels_wait_page_group_name(
        app_label, page_index, model_name, model_pk
    )
    group = Group(group_name)
    group.discard(message.reply_channel)


def connect_auto_advance(message, params):
    participant_code, page_index = params.split(',')
    page_index = int(page_index)

    group = Group('auto-advance-{}'.format(participant_code))
    group.add(message.reply_channel)

    # in case message was sent before this web socket connects

    try:
        participant = Participant.objects.get(code=participant_code)
    except Participant.DoesNotExist:
        message.reply_channel.send(
            {'text': json.dumps(
                # doesn't get shown because not yet localized
                {'error': 'Participant not found in database.'})})
        return
    if participant._index_in_pages > page_index:
        message.reply_channel.send(
            {'text': json.dumps(
                {'new_index_in_pages': participant._index_in_pages})})


def disconnect_auto_advance(message, params):
    participant_code, page_index = params.split(',')

    group = Group('auto-advance-{}'.format(participant_code))
    group.discard(message.reply_channel)


def create_session(message):
    group = Group(message['channels_group_name'])

    kwargs = message['kwargs']
    try:
        otree.session.create_session(**kwargs)
    except Exception as e:
        error_message = 'Failed to create session: "{}" - Check the server logs'.format(
                    str(e))
        group.send(
            {'text': json.dumps(
                {'error': error_message})}
        )
        FailedSessionCreation.objects.create(
            pre_create_id=kwargs['_pre_create_id'],
            message=error_message[:FAILURE_MESSAGE_MAX_LENGTH]
        )
        raise

    group.send(
        {'text': json.dumps(
            {'status': 'ready'})}
    )

    if 'room' in kwargs:
        room_name = kwargs['room'].name
        Group('room-{}-participants'.format(room_name)).send(
            {'text': json.dumps(
                {'status': 'session_ready'})}
        )
        ParticipantVisit.objects.filter(room_name=room_name).delete()


def connect_wait_for_session(message, pre_create_id):
    group = Group(channels_create_session_group_name(pre_create_id))
    group.add(message.reply_channel)

    # in case message was sent before this web socket connects
    if Session.objects.filter(_pre_create_id=pre_create_id):
        group.send(
        {'text': json.dumps(
            {'status': 'ready'})}
        )
    else:
        failures = FailedSessionCreation.objects.filter(
            pre_create_id=pre_create_id
        )
        if failures:
            failure = failures[0]
            group.send(
                {'text': json.dumps(
                    {'error': failure.message})}
            )


def disconnect_wait_for_session(message, pre_create_id):
    group = Group(
        channels_create_session_group_name(pre_create_id)
    )
    group.discard(message.reply_channel)


def connect_room_admin(message, room):
    Group('room-admin-{}'.format(room)).add(message.reply_channel)

    room = ROOM_DICT[room]
    all_participant_list = room.get_participant_labels()
    with lock_on_this_code_path():
        participant_list = list(ParticipantVisit.objects.filter(room_name=room).distinct().values_list('participant_id', flat=True))
        not_present_list = all_participant_list - participant_list

        message.reply_channel.send({'text': json.dumps({
            'status': 'load_participant_lists',
            'participants_present': participant_list,
            'participants_not_present': None
        })})


def disconnect_room_admin(message, room):
    Group('room-admin-{}'.format(room)).discard(message.reply_channel)


def connect_room_participant(message, params):
    args = params.split(',')
    room_name = args[0]
    participant_label = args[1]

    room = ROOM_DICT[room_name]
    if room.has_session():
        message.reply_channel.send("session_ready")
    else:
        with lock_on_this_code_path():
            Group('room-{}-participants'.format(room_name)).add(message.reply_channel)

            ParticipantVisit(participant_id=participant_label, room_name=room_name).save()

            Group('room-admin-{}'.format(room_name)).send({'text': json.dumps({
                'status': 'add_participant',
                'participant': participant_label,
                'has_participant_labels_list': room.has_participant_labels()
            })})


def disconnect_room_participant(message, params):
    args = params.split(',')
    room_name = args[0]
    participant_label = args[1]

    room = ROOM_DICT[room_name]
    try:
        with lock_on_this_code_path():
            Group('room-{}-participants'.format(room_name)).discard(message.reply_channel)

            ParticipantVisit.objects.get(participant_id=participant_label, room_name=room_name).delete()

            Group('room-admin-{}'.format(room_name)).send({'text': json.dumps({
                'status': 'remove_participant',
                'participant': participant_label,
                'has_participant_labels_list': room.has_participant_labels()
            })})
    except IndexError:
        # This error will occur for every participant when they are forwarded from the wait page to a new session
        pass
