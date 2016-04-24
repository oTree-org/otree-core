from channels import Group
from otree.models import Participant
from otree import common_internal
from otree.common_internal import (
    channels_wait_page_group_name,
    channels_create_session_group_name,
)
import sys
import json
import otree.session
from otree.views.demo import get_session
from otree.models import Session
from otree.models_concrete import FailedSessionCreation


if sys.version_info[0] == 2:
    from urlparse import parse_qs
else:
    from urllib.parse import parse_qs


def connect_wait_page(message, params):
    app_label, page_index, model_name, model_pk = params.split(',')
    page_index = int(page_index)
    model_pk = int(model_pk)


    group_name = channels_wait_page_group_name(
        app_label, page_index, model_name, model_pk
    )
    group = Group(group_name)
    group.add(message.reply_channel)

    # in case message was sent before this web socket connects
    # fixme: app name or app label?
    models_module = common_internal.get_models_module(app_label)

    GroupOrSubsession = {
        'subsession': getattr(models_module, 'Subsession'),
        'group': getattr(models_module, 'Group')
    }[model_name]

    group_or_subsession = GroupOrSubsession.objects.get(pk=model_pk)

    participants_for_this_page = set(
        p.participant for p in group_or_subsession.player_set.all()
    )

    unvisited = set(
        p for p in participants_for_this_page if
        p._index_in_pages < page_index
    )

    if not unvisited:
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
    participant = Participant.objects.get(code=participant_code)
    if participant._index_in_pages > page_index:
        message.reply_channel.send(
            {'text': json.dumps(
                {'new_index_in_pages': participant._index_in_pages})}
        )


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
        group.send(
            {'text': json.dumps(
                {'error': 'Failed to create session. Check the server logs.'})}
        )
        FailedSessionCreation(pre_create_id=kwargs['_pre_create_id']).save()
        raise e

    group.send(
        {'text': json.dumps(
            {'status': 'ready'})}
)


def connect_wait_for_session(message, pre_create_id):
    group = Group(channels_create_session_group_name(pre_create_id))
    group.add(message.reply_channel)

    # in case message was sent before this web socket connects
    if Session.objects.filter(_pre_create_id=pre_create_id):
        group.send(
        {'text': json.dumps(
            {'status': 'ready'})}
        )
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


def connect_wait_for_demo_session(message, session_config_name):
    group = Group(channels_create_demo_session_group_name(session_config_name))
    group.add(message.reply_channel)

    # redundant check in case race condition
    if get_session(session_config_name):
        group.send(
            {'text': json.dumps(
                {'status': 'ready'})}
            )


def disconnect_wait_for_demo_session(message, session_config_name):
    group = Group(channels_create_demo_session_group_name(session_config_name))
    group.discard(message.reply_channel)

'''
def connect_admin_lobby(message):

    Group('admin_lobby').add(message.)
    ids = ParticipantVisit.objects.all()
    Group('admin_lobby').send(ids)


def connect_participant_lobby(message):
    group = Group('room-{}-participants')
    group.add(message.reply_channel)
    ParticipantVisit(participant_id).save()
    Group('admin_lobby').send({'participant': participant_id})

def disconnect_participant_lobby(message):
    group = Group('room-{}-participants')
    group.discard(message.reply_channel)
    Group('admin_lobby').send({'participant': participant_id, 'action': 'Leaving'})
    ParticipantVisit(participant_id).delete()

'''