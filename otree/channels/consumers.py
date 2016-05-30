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
from otree.models_concrete import FailedSessionCreation


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
    except:
        group.send(
            {'text': json.dumps(
                # doesn't get shown because not yet localized
                {'error': 'Failed to create session. Check the server logs.'})}
        )
        FailedSessionCreation(pre_create_id=kwargs['_pre_create_id']).save()
        raise
    group.send({'text': json.dumps({'status': 'ready'})})


def connect_wait_for_session(message, pre_create_id):
    group = Group(channels_create_session_group_name(pre_create_id))
    group.add(message.reply_channel)

    # in case message was sent before this web socket connects
    if Session.objects.filter(_pre_create_id=pre_create_id):
        group.send({'text': json.dumps({'status': 'ready'})})
    elif FailedSessionCreation.objects.filter(
        pre_create_id=pre_create_id
    ).exists():
        group.send(
            {'text': json.dumps(
                {'error': 'Failed to create session. Check the server logs.'})}
        )


def disconnect_wait_for_session(message, pre_create_id):
    group = Group(
        channels_create_session_group_name(pre_create_id)
    )
    group.discard(message.reply_channel)


# def connect_admin_lobby(message):

    # Group('admin_lobby').add(message.)
    # ids = ParticipantVisit.objects.all()
    # Group('admin_lobby').send(ids)


# def connect_participant_lobby(message):

    # ParticipantVisit(participant_id).save()
    # Group('admin_lobby').send({'participant': participant_id})

# def disconnect_participant_lobby(message):

    # Group('admin_lobby').send(
    #     {'participant': participant_id, 'action': 'Leaving'})
    # ParticipantVisit(participant_id).delete()
