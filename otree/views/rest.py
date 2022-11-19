import json
from pathlib import Path
from importlib import import_module

from starlette.requests import Request
from starlette.responses import Response, JSONResponse

import otree
import otree.bots.browser
import otree.views.cbv
from otree import settings
from otree.channels import utils as channel_utils
from otree.common import GlobalState, get_models_module
from otree.currency import json_dumps
from otree.database import db, dbq
from otree.models import Session, Participant
from otree.models_concrete import ParticipantVarsFromREST
from otree.room import ROOM_DICT
from otree.session import create_session, SESSION_CONFIGS_DICT, CreateSessionInvalidArgs
from otree.templating import ibis_loader

from .cbv import BaseRESTView


class RESTOTreeVersion(BaseRESTView):
    url_pattern = '/api/otree_version'

    def get(self):
        return JSONResponse(dict(version=otree.__version__))


class RESTSessionConfigs(BaseRESTView):
    url_pattern = '/api/session_configs'

    def get(self):
        return Response(json_dumps(list(SESSION_CONFIGS_DICT.values())))


class RESTRooms(BaseRESTView):
    url_pattern = '/api/rooms'

    def get(self):
        data = [r.rest_api_dict(self.request) for r in ROOM_DICT.values()]
        return JSONResponse(data)


class RESTSessionVars(BaseRESTView):

    url_pattern = '/api/session_vars/{code}'

    def post(self, vars):
        code = self.request.path_params['code']
        session = db.get_or_404(Session, code=code)
        session.vars.update(vars)
        return JSONResponse({})


class RESTParticipantVars(BaseRESTView):

    url_pattern = '/api/participant_vars/{code}'

    def post(self, vars):
        code = self.request.path_params['code']
        participant = db.get_or_404(Participant, code=code)
        participant.vars.update(vars)
        return JSONResponse({})


class RESTParticipantVarsByRoom(BaseRESTView):
    """
    This can be used when you don't know the participant code,
    or when the participant doesn't have a code yet.
    For example, you might need to send data to oTree about the participant
    BEFORE sending the participant to oTree via their room link.
    """

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
        kwargs = dict(
            participant_label=participant_label,
            room_name=room_name,
        )
        _json_data = json.dumps(vars)
        obj = ParticipantVarsFromREST.objects_first(**kwargs)
        if obj:
            obj._json_data = _json_data
        else:
            obj = ParticipantVarsFromREST(**kwargs, _json_data=_json_data)
            db.add(obj)
        return JSONResponse({})


class RESTSessions(BaseRESTView):

    url_pattern = '/api/sessions'

    def get(self):
        sessions = []
        for session in dbq(Session).filter_by(is_demo=False).order_by('id'):
            session_dict = session_attrs_for_list(session)
            session_dict.update(get_session_urls(session, self.request))
            sessions.append(session_dict)
        return JSONResponse(sessions)

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


def session_attrs_for_list(session: Session):
    # this should include fields that help you distinguish it from other sessions

    return dict(
        code=session.code,
        num_participants=session.num_participants,
        created_at=session._created,
        label=session.label,
        config_name=session.config['name'],
    )


def session_attrs_for_detail(session: Session):
    return dict(
        # we need the session config for mturk settings and participation fee
        # technically, other parts of session config might not be JSON serializable
        config=session.config,
        REAL_WORLD_CURRENCY_CODE=settings.REAL_WORLD_CURRENCY_CODE,
    )


class RESTGetSessionInfo(BaseRESTView):
    # it's more of GET semantics but we need to use POST because we pass request.body
    url_pattern = '/api/get_session/{code}'

    def post(self, participant_labels=None, participant_vars=None, session_vars=None):
        if participant_vars is None:
            participant_vars = []
        if session_vars is None:
            session_vars = []
        code = self.request.path_params['code']
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
            # special case participant field.
            # if
            if 'finished' in settings.PARTICIPANT_FIELDS:
                pdata['finished'] = pp.vars.get('finished', False)
            # shouldn't raise an error if the field is not found,
            # e.g. because oTree Hub may check if some things are defined to provide
            # extra functionality.
            # there is no silent failure because we will just not include that key
            # in the output, so it will be obvious.
            for field in participant_vars:
                if field in pp.vars:
                    val = pp.vars[field]
                    try:
                        json_dumps(val)
                    except TypeError:
                        return Response(
                            f"participant.vars['{field}'] is not JSON serializable",
                            status_code=400,
                        )
                    pdata[field] = val

            pdata_list.append(pdata)

        payload = session_attrs_for_list(session)
        payload.update(session_attrs_for_detail(session))
        payload.update(get_session_urls(session, self.request))
        payload.update(
            config=session.config,
            participants=pdata_list,
            REAL_WORLD_CURRENCY_CODE=settings.REAL_WORLD_CURRENCY_CODE,
        )

        for field in session_vars:
            if field in session.vars:
                val = session.vars[field]
                try:
                    json_dumps(val)
                except TypeError:
                    return Response(
                        f"session.vars['{field}'] is not JSON serializable",
                        status_code=400,
                    )
                payload[field] = val

        mturk_settings = session.config.get('mturk_hit_settings')
        if mturk_settings:
            payload['mturk_template_html'] = ibis_loader.search_template(
                mturk_settings['template']
            ).read_text('utf8')

        # need custom json_dumps for currency values
        return Response(json_dumps(payload))


class RESTGetSessionInfoLegacy(BaseRESTView):
    # for compat.
    # it used to be GET, but since it uses request.body changed to POST.
    url_pattern = '/api/sessions/{code}'
    get = RESTGetSessionInfo.post


launcher_session_code = None


class CreateBrowserBotsSession(BaseRESTView):
    url_pattern = '/create_browser_bots_session'

    def post(
        self,
        num_participants,
        session_config_name,
        case_number,
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


class RESTApps(BaseRESTView):
    url_pattern = '/api/apps'

    def get(self):
        from otree.settings import OTREE_APPS

        d = {}
        for app in OTREE_APPS:
            models_module = get_models_module(app)
            d[app] = getattr(models_module, 'doc', '')
        return Response(json_dumps(d))
