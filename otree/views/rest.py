import json

import vanilla
from django.http import HttpResponse, JsonResponse, HttpResponseNotFound

import otree
from otree.channels import utils as channel_utils
import otree.bots.browser
from otree.models_concrete import (
    ParticipantVarsFromREST,
    BrowserBotsLauncherSessionCode,
)
from otree.room import ROOM_DICT
from otree.session import create_session
from otree.views.abstract import BaseRESTView


class PostParticipantVarsThroughREST(BaseRESTView):

    url_pattern = r'^api/participant_vars/$'

    def inner_post(self, room_name, participant_label, vars):
        if room_name not in ROOM_DICT:
            return HttpResponseNotFound(f'Room {room_name} not found')
        room = ROOM_DICT[room_name]
        session = room.get_session()
        if session:
            participant = session.participant_set.filter(
                label=participant_label
            ).first()
            if participant:
                participant.vars.update(vars)
                participant.save()
                return HttpResponse('ok')
        obj, _ = ParticipantVarsFromREST.objects.update_or_create(
            participant_label=participant_label,
            room_name=room_name,
            defaults=dict(_json_data=json.dumps(vars)),
        )
        return HttpResponse('ok')


class RESTSessionVars(BaseRESTView):
    url_pattern = r'^api/session_vars/$'

    def inner_post(self, room_name, vars):
        if room_name not in ROOM_DICT:
            return HttpResponseNotFound(f'Room {room_name} not found')
        room = ROOM_DICT[room_name]
        session = room.get_session()
        if not session:
            return HttpResponseNotFound(f'No current session in room {room_name}')
        session.vars.update(vars)
        session.save()
        return HttpResponse('ok')


class RESTCreateSession(BaseRESTView):

    url_pattern = r'^api/sessions/$'

    def inner_post(self, **kwargs):
        '''
        Notes:
        - This allows you to pass parameters that did not exist in the original config,
        as well as params that are blocked from editing in the UI,
        either because of datatype.
        I can't see any specific problem with this.
        '''
        session = create_session(**kwargs)
        room_name = kwargs.get('room_name')
        if room_name:
            channel_utils.sync_group_send_wrapper(
                type='room_session_ready',
                group=channel_utils.room_participants_group_name(room_name),
                event={},
            )
        return HttpResponse(session.code)


class RESTCreateSessionLegacy(RESTCreateSession):
    url_pattern = r'^api/v1/sessions/$'


class RESTSessionVarsLegacy(RESTSessionVars):
    url_pattern = r'^api/v1/session_vars/$'


class RESTParticipantVarsLegacy(PostParticipantVarsThroughREST):
    url_pattern = r'^api/v1/participant_vars/$'


class CreateBrowserBotsSession(BaseRESTView):
    url_pattern = r"^create_browser_bots_session/$"

    def inner_post(
        self, num_participants, session_config_name, case_number, pre_create_id
    ):
        session = create_session(
            session_config_name=session_config_name, num_participants=num_participants
        )
        otree.bots.browser.initialize_session(
            session_pk=session.pk, case_number=case_number
        )
        BrowserBotsLauncherSessionCode.objects.update_or_create(
            # i don't know why the update_or_create arg is called 'defaults'
            # because it will update even if the instance already exists
            # maybe for consistency with get_or_create
            defaults=dict(code=session.code, pre_create_id=pre_create_id)
        )
        channel_utils.sync_group_send_wrapper(
            type='browserbot_sessionready', group='browser_bot_wait', event={}
        )

        return HttpResponse(session.code)


class CloseBrowserBotsSession(BaseRESTView):
    url_pattern = r"^close_browser_bots_session/$"

    def inner_post(self, **kwargs):
        BrowserBotsLauncherSessionCode.objects.all().delete()
        return HttpResponse('ok')
