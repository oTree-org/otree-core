import json
from otree.common import GlobalState
import otree.views.cbv
from starlette.responses import Response
from otree.database import db, dbq
import otree
from otree.channels import utils as channel_utils
import otree.bots.browser
from otree.models_concrete import ParticipantVarsFromREST
from otree.room import ROOM_DICT
from otree.session import create_session
from .cbv import BaseRESTView


class PostParticipantVarsThroughREST(BaseRESTView):

    url_pattern = '/api/participant_vars'

    def inner_post(self, room_name, participant_label, vars):
        if room_name not in ROOM_DICT:
            return Response(f'Room {room_name} not found', status_code=404)
        room = ROOM_DICT[room_name]
        session = room.get_session()
        if session:
            participant = session.pp_set.filter_by(label=participant_label).first()
            if participant:
                participant.vars.update(vars)
                return Response('ok')
        kwargs = dict(participant_label=participant_label, room_name=room_name,)
        _json_data = json.dumps(vars)
        obj = ParticipantVarsFromREST.objects_first(**kwargs)
        if obj:
            obj._json_data = _json_data
        else:
            obj = ParticipantVarsFromREST(**kwargs, _json_data=_json_data)
            db.add(obj)
        return Response('ok')


class RESTSessionVars(BaseRESTView):
    url_pattern = '/api/session_vars'

    def inner_post(self, room_name, vars):
        if room_name not in ROOM_DICT:
            return Response(f'Room {room_name} not found', status_code=404)
        room = ROOM_DICT[room_name]
        session = room.get_session()
        if not session:
            return Response(f'No current session in room {room_name}', 404)
        session.vars.update(vars)
        return Response('ok')


class RESTCreateSession(BaseRESTView):

    url_pattern = '/api/sessions'

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
            channel_utils.sync_group_send(
                group=channel_utils.room_participants_group_name(room_name),
                data={'status': 'session_ready'},
            )
        return Response(session.code)


class RESTCreateSessionLegacy(RESTCreateSession):
    url_pattern = '/api/v1/sessions'


class RESTSessionVarsLegacy(RESTSessionVars):
    url_pattern = '/api/v1/session_vars'


class RESTParticipantVarsLegacy(PostParticipantVarsThroughREST):
    url_pattern = '/api/v1/participant_vars'


launcher_session_code = None


class CreateBrowserBotsSession(BaseRESTView):
    url_pattern = '/create_browser_bots_session'

    def inner_post(
        self, num_participants, session_config_name, case_number,
    ):
        session = create_session(
            session_config_name=session_config_name, num_participants=num_participants
        )
        otree.bots.browser.initialize_session(
            session_pk=session.id, case_number=case_number
        )
        GlobalState.browser_bots_launcher_session_code = session.code
        channel_utils.sync_group_send(
            group='browser_bot_wait', data={'status': 'session_ready'}
        )

        return Response(session.code)


class CloseBrowserBotsSession(BaseRESTView):
    url_pattern = '/close_browser_bots_session'

    def inner_post(self, **kwargs):
        GlobalState.browser_bots_launcher_session_code = None
        return Response('ok')
