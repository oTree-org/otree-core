import json
from pathlib import Path

from starlette.requests import Request
from starlette.responses import Response, JSONResponse

import otree
import otree.bots.browser
import otree.views.cbv
from otree import settings
from otree.channels import utils as channel_utils
from otree.common import GlobalState
from otree.currency import json_dumps
from otree.database import db
from otree.models import Session, Participant
from otree.models_concrete import ParticipantVarsFromREST
from otree.room import ROOM_DICT
from otree.session import create_session, SESSION_CONFIGS_DICT, CreateSessionInvalidArgs
from otree.templating import ibis_loader

from .cbv import BaseRESTView


class PostParticipantVarsThroughREST(BaseRESTView):

    url_pattern = '/api/participant_vars'

    def post(self, room_name, participant_label, vars):
        if room_name not in ROOM_DICT:
            return Response(f'Room {room_name} not found', status_code=404)
        room = ROOM_DICT[room_name]
        session = room.get_session()
        if session:
            participant = session.pp_set.filter_by(label=participant_label).first()
            if participant:
                participant.vars.update(vars)
                return JSONResponse({})
        kwargs = dict(participant_label=participant_label, room_name=room_name,)
        _json_data = json.dumps(vars)
        obj = ParticipantVarsFromREST.objects_first(**kwargs)
        if obj:
            obj._json_data = _json_data
        else:
            obj = ParticipantVarsFromREST(**kwargs, _json_data=_json_data)
            db.add(obj)
        return JSONResponse({})


class RESTSessionVars(BaseRESTView):
    url_pattern = '/api/session_vars'

    def post(self, vars, code=None, room_name=None):
        if not (code or room_name):
            return Response(
                f"You must pass either 'code' or 'room_name'", status_code=404
            )
        if code:
            session = Session.objects_get(code=code)
        else:
            if room_name not in ROOM_DICT:
                return Response(f'Room {room_name} not found', status_code=404)
            room = ROOM_DICT[room_name]
            session = room.get_session()
            if not session:
                return Response(f'No current session in room {room_name}', 404)
        session.vars.update(vars)
        return JSONResponse({})


def get_session_urls(session: Session, request: Request) -> dict:
    d = dict(
        session_wide_url=request.url_for(
            'JoinSessionAnonymously', anonymous_code=session._anonymous_code
        ),
        admin_url=request.url_for('SessionStartLinks', code=session.code),
    )
    room = session.get_room()
    if room:
        d['room_url'] = room.get_room_wide_url(request)
    return d


class RESTGetSessionInfo(BaseRESTView):
    url_pattern = '/api/session'

    def get(self, code, participant_labels=None):
        session = db.get_or_404(Session, code=code)
        pp_set = session.pp_set
        if participant_labels is not None:
            pp_set = pp_set.filter(Participant.label.in_(participant_labels))
        pdata_list = []
        for pp in pp_set:
            pdata = dict(
                id_in_session=pp.id_in_session,
                code=pp.code,
                label=pp.label,
                payoff_in_real_world_currency=pp.payoff.to_real_world_currency(session),
            )
            if 'finished' in settings.PARTICIPANT_FIELDS:
                pdata['finished'] = pp.vars.get('finished', False)
            pdata_list.append(pdata)

        payload = dict(
            # we need the session config for mturk settings and participation fee
            # technically, other parts of session config might not be JSON serializable
            config=session.config,
            num_participants=session.num_participants,
            REAL_WORLD_CURRENCY_CODE=settings.REAL_WORLD_CURRENCY_CODE,
            participants=pdata_list,
            **get_session_urls(session, self.request),
        )

        mturk_settings = session.config.get('mturk_hit_settings')
        if mturk_settings:
            payload['mturk_template_html'] = ibis_loader.search_template(
                mturk_settings['template']
            ).read_text('utf8')

        # need custom json_dumps for currency values
        return Response(json_dumps(payload))


class RESTCreateSession(BaseRESTView):

    url_pattern = '/api/sessions'

    def post(self, **kwargs):
        try:
            session = create_session(**kwargs)
        except CreateSessionInvalidArgs as exc:
            return Response(str(exc), status_code=400)
        room_name = kwargs.get('room_name')

        response_payload = dict(code=session.code)
        if room_name:
            channel_utils.sync_group_send(
                group=channel_utils.room_participants_group_name(room_name),
                data={'status': 'session_ready'},
            )

        response_payload.update(get_session_urls(session, self.request))

        return JSONResponse(response_payload)


class RESTSessionConfigs(BaseRESTView):
    url_pattern = '/api/session_configs'

    def get(self):
        return Response(json_dumps(list(SESSION_CONFIGS_DICT.values())))


class RESTOTreeVersion(BaseRESTView):
    url_pattern = '/api/otree_version'

    def get(self):
        return JSONResponse(dict(version=otree.__version__))


class RESTCreateSessionLegacy(RESTCreateSession):
    url_pattern = '/api/v1/sessions'


class RESTSessionVarsLegacy(RESTSessionVars):
    url_pattern = '/api/v1/session_vars'


class RESTParticipantVarsLegacy(PostParticipantVarsThroughREST):
    url_pattern = '/api/v1/participant_vars'


launcher_session_code = None


class CreateBrowserBotsSession(BaseRESTView):
    url_pattern = '/create_browser_bots_session'

    def post(
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

    def post(self, **kwargs):
        GlobalState.browser_bots_launcher_session_code = None
        return Response('ok')
