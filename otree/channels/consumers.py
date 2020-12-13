import base64
import datetime
import io
import logging
import time
import traceback
import urllib.parse

import django.db
import django.utils.timezone
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer, WebsocketConsumer
from django.conf import settings
from django.core.signing import Signer, BadSignature
from django.shortcuts import reverse

from otree.live import live_payload_function
import otree.bots.browser
import otree.channels.utils as channel_utils
import otree.session
from otree.channels.utils import get_chat_group
from otree.common import get_models_module, json_dumps
from otree.export import export_wide, export_app, custom_export_app
from otree.models import Participant, Session
from otree.models_concrete import (
    CompletedGroupWaitPage,
    CompletedSubsessionWaitPage,
    CompletedGBATWaitPage,
    ChatMessage,
)
from otree.models_concrete import ParticipantRoomVisit, BrowserBotsLauncherSessionCode
from otree.room import ROOM_DICT
from otree.session import SESSION_CONFIGS_DICT
from otree.views.admin import CreateSessionForm

logger = logging.getLogger(__name__)

ALWAYS_UNRESTRICTED = 'ALWAYS_UNRESTRICTED'
UNRESTRICTED_IN_DEMO_MODE = 'UNRESTRICTED_IN_DEMO_MODE'


class InvalidWebSocketParams(Exception):
    '''exception to raise when websocket params are invalid'''


class _OTreeAsyncJsonWebsocketConsumer(AsyncJsonWebsocketConsumer):
    """
    This is not public API, might change at any time.
    """

    def clean_kwargs(self, **kwargs):
        '''
        subclasses should override if the route receives a comma-separated params arg.
        otherwise, this just passes the route kwargs as is (usually there is just one).
        The output of this method is passed to self.group_name(), self.post_connect,
        and self.pre_disconnect, so within each class, all 3 of those methods must
        accept the same args (or at least take a **kwargs wildcard, if the args aren't used)
        '''
        return kwargs

    def group_name(self, **kwargs):
        raise NotImplementedError()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleaned_kwargs = self.clean_kwargs(**self.scope['url_route']['kwargs'])
        group_name = self.group_name(**self.cleaned_kwargs)
        self.groups = [group_name] if group_name else []

    unrestricted_when = ''

    # async def dispatch(self, message):
    #     with dispatch_lock:
    #         return super().dispatch(message)

    # there is no login_required for channels
    # so we need to make our own
    # https://github.com/django/channels/issues/1241
    async def connect(self):
        AUTH_LEVEL = settings.AUTH_LEVEL

        auth_required = (
            (not self.unrestricted_when)
            and AUTH_LEVEL
            or self.unrestricted_when == UNRESTRICTED_IN_DEMO_MODE
            and AUTH_LEVEL == 'STUDY'
        )

        if auth_required and not self.scope['user'].is_staff:
            msg = 'rejected un-authenticated access to websocket path {}'.format(
                self.scope['path']
            )
            logger.error(msg)
            # consider also self.accept() then send error message then self.close(code=1008)
            # this only affects otree core websockets.
        else:
            # need to accept no matter what, so we can at least send
            # an error message
            await self.accept()
            await self.post_connect(**self.cleaned_kwargs)

    async def post_connect(self, **kwargs):
        pass

    async def disconnect(self, message, **kwargs):
        await self.pre_disconnect(**self.cleaned_kwargs)

    async def pre_disconnect(self, **kwargs):
        pass

    async def receive_json(self, content, **etc):
        await self.post_receive_json(content, **self.cleaned_kwargs)

    async def post_receive_json(self, content, **kwargs):
        pass

    # can't override send(), because send_json calls super().send.
    # this override causes another error:
    # TypeError: An asyncio.Future, a coroutine or an awaitable is required
    # async def send_json(self, content, close=False):
    #     # https://github.com/encode/uvicorn/issues/757
    #     try:
    #         await super().send_json(content, close)
    #     except websockets.exceptions.ConnectionClosedError:
    #         pass


class BaseWaitPage(_OTreeAsyncJsonWebsocketConsumer):
    unrestricted_when = ALWAYS_UNRESTRICTED
    kwarg_names: list

    def clean_kwargs(self):
        d = parse_querystring(self.scope['query_string'])
        kwargs = {}
        for k in self.kwarg_names:
            kwargs[k] = int(d[k])
        return kwargs

    async def wait_page_ready(self, event=None):
        await self.send_json({'status': 'ready'})


class SubsessionWaitPage(BaseWaitPage):

    kwarg_names = ('session_pk', 'page_index', 'participant_id')

    def group_name(self, session_pk, page_index, participant_id):
        return channel_utils.subsession_wait_page_name(session_pk, page_index)

    def completion_exists(self, **kwargs):
        return CompletedSubsessionWaitPage.objects.filter(**kwargs).exists()

    async def post_connect(self, session_pk, page_index, participant_id):
        if await database_sync_to_async(self.completion_exists)(
            page_index=page_index, session_id=session_pk
        ):
            await self.wait_page_ready()


class GroupWaitPage(BaseWaitPage):

    kwarg_names = SubsessionWaitPage.kwarg_names + ('group_id',)

    def group_name(self, session_pk, page_index, group_id, participant_id):
        return channel_utils.group_wait_page_name(session_pk, page_index, group_id)

    def completion_exists(self, **kwargs):
        return CompletedGroupWaitPage.objects.filter(**kwargs).exists()

    async def post_connect(self, session_pk, page_index, group_id, participant_id):
        if await database_sync_to_async(self.completion_exists)(
            page_index=page_index, group_id=group_id, session_id=session_pk
        ):
            await self.wait_page_ready()


class LiveConsumer(_OTreeAsyncJsonWebsocketConsumer):
    unrestricted_when = ALWAYS_UNRESTRICTED

    def group_name(self, session_code, page_index, **kwargs):
        return channel_utils.live_group(session_code, page_index)

    def clean_kwargs(self):
        return parse_querystring(self.scope['query_string'])

    def browser_bot_exists(self, participant_code):
        # for browser bots, block liveSend calls that get triggered on page load.
        # instead, everything must happen through call_live_method in a controlled way.
        return Participant.objects.filter(
            code=participant_code, is_browser_bot=True
        ).exists()

    async def post_receive_json(self, content, participant_code, page_name, **kwargs):
        if await database_sync_to_async(self.browser_bot_exists)(participant_code):
            return
        await database_sync_to_async(live_payload_function)(
            participant_code=participant_code, page_name=page_name, payload=content
        )

    @classmethod
    async def encode_json(cls, content):
        return json_dumps(content)

    async def send_back_to_client(self, event):
        pcode = self.cleaned_kwargs['participant_code']
        if pcode in event:
            await self.send_json(event[pcode])


class GroupByArrivalTime(_OTreeAsyncJsonWebsocketConsumer):

    unrestricted_when = ALWAYS_UNRESTRICTED

    app_name: str
    player_id: int

    def clean_kwargs(self):
        d = parse_querystring(self.scope['query_string'])
        return {
            'app_name': d['app_name'],
            'session_pk': int(d['session_pk']),
            'participant_id': int(d['participant_id']),
            'page_index': int(d['page_index']),
            'player_id': int(d['player_id']),
        }

    def group_name(self, app_name, player_id, page_index, session_pk, participant_id):
        gn = channel_utils.gbat_group_name(session_pk, page_index)
        return gn

    def is_ready(self, *, app_name, player_id, page_index, session_pk):
        models_module = get_models_module(app_name)
        group_id_in_subsession = (
            models_module.Group.objects.filter(player__id=player_id)
            .values_list('id_in_subsession', flat=True)
            .get()
        )

        return CompletedGBATWaitPage.objects.filter(
            page_index=page_index,
            id_in_subsession=int(group_id_in_subsession),
            session_id=session_pk,
        ).exists()

    def mark_ready_status(self, is_ready):
        Participant.objects.filter(id=self.participant_id).update(
            _gbat_is_waiting=is_ready
        )

    async def post_connect(
        self, app_name, player_id, page_index, session_pk, participant_id
    ):
        self.app_name = app_name
        self.player_id = player_id
        self.participant_id = participant_id
        await database_sync_to_async(self.mark_ready_status)(True)
        if await database_sync_to_async(self.is_ready)(
            app_name=app_name,
            player_id=player_id,
            page_index=page_index,
            session_pk=session_pk,
        ):
            await self.gbat_ready()

    async def gbat_ready(self, event=None):
        await self.send_json({'status': 'ready'})

    async def pre_disconnect(
        self, app_name, player_id, page_index, session_pk, participant_id
    ):
        await database_sync_to_async(self.mark_ready_status)(False)


class DetectAutoAdvance(_OTreeAsyncJsonWebsocketConsumer):

    unrestricted_when = ALWAYS_UNRESTRICTED

    def clean_kwargs(self):
        d = parse_querystring(self.scope['query_string'])
        return {
            'participant_code': d['participant_code'],
            'page_index': int(d['page_index']),
        }

    def group_name(self, page_index, participant_code):
        return channel_utils.auto_advance_group(participant_code)

    def page_should_be_on(self, participant_code):
        try:
            return (
                Participant.objects.filter(code=participant_code)
                .values_list('_index_in_pages', flat=True)
                .get()
            )
        except Participant.DoesNotExist:
            return

    async def post_connect(self, page_index, participant_code):
        # in case message was sent before this web socket connects
        page_should_be_on = await database_sync_to_async(self.page_should_be_on)(
            participant_code
        )
        if page_should_be_on is None:
            await self.send_json({'error': 'Participant not found in database.'})
        elif page_should_be_on > page_index:
            await self.auto_advanced()

    async def auto_advanced(self, event=None):
        await self.send_json({'auto_advanced': True})


class BaseCreateSession(_OTreeAsyncJsonWebsocketConsumer):
    def group_name(self, **kwargs):
        return None

    async def send_response_to_browser(self, event: dict):
        raise NotImplemented

    async def create_session_then_send_start_link(
        self, use_browser_bots, **session_kwargs
    ):
        try:
            session = await database_sync_to_async(
                otree.session.create_session_traceback_wrapper
            )(**session_kwargs)

            if use_browser_bots:
                await database_sync_to_async(otree.bots.browser.initialize_session)(
                    session_pk=session.pk, case_number=None
                )
            # the "elif" is because if it uses browser bots, then exogenous data is mocked
            # as part of run_bots.
            # 2020-07-07: this queries the DB, shouldn't i use database_sync_to_async?
            # i don't get any error
            elif session.is_demo:
                await database_sync_to_async(session.mock_exogenous_data)()
        except Exception as e:
            if isinstance(e, otree.session.CreateSessionError):
                e = e.__cause__
            traceback_str = ''.join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )
            await self.send_response_to_browser(
                dict(error=f'Failed to create session: {e}', traceback=traceback_str)
            )

            # i used to do "raise" here.
            # if I raise, then in non-demo sessions, the traceback is not displayed
            # as it should be.
            # Instead, there is an error
            # "Server error occurred, check Sentry or the logs"
            # I guess the websocket gets cut off? that's also why my test_traceback test was failing.
            # why did I use raise in the first place?
            # was it just so the traceback would go to the console or Sentry?
            # if we show it in the browser, there's no need to show it anywhere else, right?
            # maybe it was just a fallback in case the TB was truncated?
            # or because the traceback should not be shown outside of DEBUG mode
        else:
            session_home_view = (
                'MTurkCreateHIT' if session.is_mturk else 'SessionStartLinks'
            )

            await self.send_response_to_browser(
                {'session_url': reverse(session_home_view, args=[session.code])}
            )


class CreateDemoSession(BaseCreateSession):

    unrestricted_when = UNRESTRICTED_IN_DEMO_MODE

    async def send_response_to_browser(self, event: dict):
        await self.send_json(event)

    async def post_receive_json(self, form_data: dict):
        session_config_name = form_data['session_config']
        config = SESSION_CONFIGS_DICT.get(session_config_name)
        if not config:
            msg = f'Session config "{session_config_name}" does not exist.'
            await self.send_json({'validation_errors': msg})
            return

        num_participants = config['num_demo_participants']
        use_browser_bots = config.get('use_browser_bots', False)

        await self.create_session_then_send_start_link(
            session_config_name=session_config_name,
            use_browser_bots=use_browser_bots,
            num_participants=num_participants,
            is_demo=True,
        )


class CreateSession(BaseCreateSession):

    unrestricted_when = None

    def group_name(self, **kwargs):
        return 'create_session'

    async def post_receive_json(self, form_data: dict):
        form = CreateSessionForm(data=form_data)
        if not form.is_valid():
            await self.send_json({'validation_errors': form.errors})
            return

        session_config_name = form.cleaned_data['session_config']
        is_mturk = form.cleaned_data['is_mturk']

        config = SESSION_CONFIGS_DICT[session_config_name]

        num_participants = form.cleaned_data['num_participants']
        if is_mturk:
            num_participants *= settings.MTURK_NUM_PARTICIPANTS_MULTIPLE

        modified_session_config_fields = {}

        for field in config.editable_fields():
            html_field_name = config.html_field_name(field)
            old_value = config[field]

            # to allow concise unit tests, we can simply omit any fields we don't
            # want to change. this allows us to write more concise
            # unit tests.
            # EXCEPT for boolean fields -- omitting
            # it means we turn it off.
            # ideally we could interpret omitted boolean fields as unchanged
            # and False as unchecked, but HTML & serializeArray omits
            # unchecked checkboxes from form data.

            if isinstance(old_value, bool):
                new_value = bool(form_data.get(html_field_name))
                if old_value != new_value:
                    modified_session_config_fields[field] = new_value
            else:
                new_value_raw = form_data.get(html_field_name, '')
                if new_value_raw != '':
                    # don't use isinstance because that will catch bool also
                    if type(old_value) is int:
                        # in case someone enters 1.0 instead of 1
                        new_value = int(float(new_value_raw))
                    else:
                        new_value = type(old_value)(new_value_raw)
                    if old_value != new_value:
                        modified_session_config_fields[field] = new_value

        use_browser_bots = modified_session_config_fields.get(
            'use_browser_bots', config.get('use_browser_bots', False)
        )

        # if room_name is missing, it will be empty string
        room_name = form.cleaned_data['room_name'] or None

        await self.create_session_then_send_start_link(
            session_config_name=session_config_name,
            num_participants=num_participants,
            is_demo=False,
            is_mturk=is_mturk,
            modified_session_config_fields=modified_session_config_fields,
            use_browser_bots=use_browser_bots,
            room_name=room_name,
        )

        if room_name:
            await channel_utils.group_send_wrapper(
                type='room_session_ready',
                group=channel_utils.room_participants_group_name(room_name),
                event={},
            )

    async def send_response_to_browser(self, event: dict):
        '''
        Send to a group instead of the channel only,
        because if the websocket disconnects during creation of a large session,
        (due to temporary network error, etc, or Heroku H15, 55 seconds without ping)
        the user could be stuck on "please wait" forever.
        the downside is that if two admins create sessions around the same time,
        your page could automatically redirect to the other admin's session.
        '''
        [group] = self.groups
        await channel_utils.group_send_wrapper(
            type='session_created', group=group, event=event
        )

    async def session_created(self, event):
        await self.send_json(event)


class SessionMonitor(_OTreeAsyncJsonWebsocketConsumer):
    unrestricted_when = UNRESTRICTED_IN_DEMO_MODE

    def group_name(self, code):
        return channel_utils.session_monitor_group_name(code)

    def get_initial_data(self, code):
        participants = Participant.objects.filter(_session_code=code, visited=True)
        return otree.export.get_rows_for_monitor(participants)

    async def post_connect(self, code):
        initial_data = await database_sync_to_async(self.get_initial_data)(code=code)
        await self.send_json(dict(rows=initial_data))

    async def monitor_table_delta(self, event):
        await self.send_json(event)

    async def update_notes(self, event):
        await self.send_json(event)


class RoomAdmin(_OTreeAsyncJsonWebsocketConsumer):

    unrestricted_when = None

    def group_name(self, room):
        return channel_utils.room_admin_group_name(room)

    def get_list(self, **kwargs):

        # make it JSON serializable
        return list(
            ParticipantRoomVisit.objects.filter(**kwargs).values_list(
                'participant_label', flat=True
            )
        )

    async def post_connect(self, room):
        room_object = ROOM_DICT[room]

        now = time.time()
        stale_threshold = now - 15
        present_list = await database_sync_to_async(self.get_list)(
            room_name=room_object.name, last_updated__gte=stale_threshold
        )

        await self.send_json(
            {'status': 'load_participant_lists', 'participants_present': present_list}
        )

        # prune very old visits -- don't want a resource leak
        # because sometimes not getting deleted on WebSocket disconnect
        very_stale_threshold = now - 10 * 60
        await database_sync_to_async(self.delete_old_visits)(
            room_name=room_object.name, last_updated__lt=very_stale_threshold
        )

    def delete_old_visits(self, **kwargs):
        ParticipantRoomVisit.objects.filter(**kwargs).delete()

    async def roomadmin_update(self, event):
        msg = {k: v for (k, v) in event.items() if k != 'type'}
        await self.send_json(msg)


class RoomParticipant(_OTreeAsyncJsonWebsocketConsumer):

    unrestricted_when = ALWAYS_UNRESTRICTED

    def clean_kwargs(self):
        d = parse_querystring(self.scope['query_string'])
        d.setdefault('participant_label', '')
        return d

    def group_name(self, room_name, participant_label, tab_unique_id):
        return channel_utils.room_participants_group_name(room_name)

    def create_participant_room_visit(self, **kwargs):
        ParticipantRoomVisit.objects.create(**kwargs)

    async def post_connect(self, room_name, participant_label, tab_unique_id):
        if room_name in ROOM_DICT:
            room = ROOM_DICT[room_name]
        else:
            # doesn't get shown because not yet localized
            await self.send_json({'error': 'Invalid room name "{}".'.format(room_name)})
            return
        if await database_sync_to_async(room.has_session)():
            await self.room_session_ready()
        else:
            try:
                await database_sync_to_async(self.create_participant_room_visit)(
                    participant_label=participant_label,
                    room_name=room_name,
                    tab_unique_id=tab_unique_id,
                    last_updated=time.time(),
                )
            except django.db.IntegrityError:
                # possible that the tab connected twice
                # without disconnecting in between
                # because of WebSocket failure
                # tab_unique_id is unique=True,
                # so this will throw an integrity error.
                # 2017-09-17: I saw the integrityerror on macOS.
                # previously, we logged this, but i see no need to do that.
                pass
            await channel_utils.group_send_wrapper(
                type='roomadmin_update',
                group=channel_utils.room_admin_group_name(room_name),
                event={'status': 'add_participant', 'participant': participant_label},
            )

    def delete_visit(self, **kwargs):
        ParticipantRoomVisit.objects.filter(**kwargs).delete()

    def visit_exists(self, **kwargs):
        return ParticipantRoomVisit.objects.filter(**kwargs).exists()

    async def pre_disconnect(self, room_name, participant_label, tab_unique_id):

        if room_name in ROOM_DICT:
            room = ROOM_DICT[room_name]
        else:
            # doesn't get shown because not yet localized
            await self.send_json({'error': 'Invalid room name "{}".'.format(room_name)})
            return

        # should use filter instead of get,
        # because if the DB is recreated,
        # the record could already be deleted
        await database_sync_to_async(self.delete_visit)(
            participant_label=participant_label,
            room_name=room_name,
            tab_unique_id=tab_unique_id,
        )

        event = {'status': 'remove_participant'}
        if room.has_participant_labels():
            if await database_sync_to_async(self.visit_exists)(
                participant_label=participant_label, room_name=room_name
            ):
                return
            # it's ok if there is a race condition --
            # in JS removing a participant is idempotent
            event['participant'] = participant_label
        admin_group = channel_utils.room_admin_group_name(room_name)

        await channel_utils.group_send_wrapper(
            group=admin_group, type='roomadmin_update', event=event
        )

    async def room_session_ready(self, event=None):
        await self.send_json({'status': 'session_ready'})


class BrowserBotsLauncher(_OTreeAsyncJsonWebsocketConsumer):

    # OK to be unrestricted because this websocket doesn't create the session,
    # or do anything sensitive.
    unrestricted_when = ALWAYS_UNRESTRICTED

    def group_name(self, session_code):
        return channel_utils.browser_bots_launcher_group(session_code)

    async def send_completion_message(self, event):
        # don't need to put in JSON since it's just a participant code
        await self.send(event['text'])


class BrowserBot(_OTreeAsyncJsonWebsocketConsumer):

    unrestricted_when = ALWAYS_UNRESTRICTED

    def group_name(self):
        return 'browser_bot_wait'

    def session_exists(self):
        return BrowserBotsLauncherSessionCode.objects.exists()

    async def post_connect(self):
        if await database_sync_to_async(self.session_exists)():
            await self.browserbot_sessionready()

    async def browserbot_sessionready(self, event=None):
        await self.send_json({'status': 'session_ready'})


class ChatConsumer(_OTreeAsyncJsonWebsocketConsumer):

    unrestricted_when = ALWAYS_UNRESTRICTED

    def clean_kwargs(self, params):

        signer = Signer(sep='/')
        try:
            original_params = signer.unsign(params)
        except BadSignature:
            raise InvalidWebSocketParams

        channel, participant_id = original_params.split('/')

        return {'channel': channel, 'participant_id': int(participant_id)}

    def group_name(self, channel, participant_id):
        return get_chat_group(channel)

    def _get_history(self, channel):
        return list(
            ChatMessage.objects.filter(channel=channel)
            .order_by('timestamp')
            .values('nickname', 'body', 'participant_id')
        )

    async def post_connect(self, channel, participant_id):

        history = await database_sync_to_async(self._get_history)(channel=channel)

        # Convert ValuesQuerySet to list
        # but is it ok to send a list (not a dict) as json?
        await self.send_json(history)

    async def post_receive_json(self, content, channel, participant_id):

        # in the Channels docs, the example has a separate msg_consumer
        # channel, so this can be done asynchronously.
        # but i think the perf is probably good enough.
        # moving into here for simplicity, especially for testing.
        nickname_signed = content['nickname_signed']
        nickname = Signer().unsign(nickname_signed)
        body = content['body']

        chat_message = dict(nickname=nickname, body=body, participant_id=participant_id)

        [group] = self.groups
        await channel_utils.group_send_wrapper(
            type='chat_sendmessages', group=group, event={'chats': [chat_message]}
        )

        await database_sync_to_async(self._create_message)(
            participant_id=participant_id, channel=channel, body=body, nickname=nickname
        )

    def _create_message(self, **kwargs):
        ChatMessage.objects.create(**kwargs)

    async def chat_sendmessages(self, event):
        chats = event['chats']
        await self.send_json(chats)


class DeleteSessions(_OTreeAsyncJsonWebsocketConsumer):
    unrestricted_when = None

    async def post_receive_json(self, content):
        Session.objects.filter(code__in=content).delete()
        await self.send_json('ok')

    def group_name(self, **kwargs):
        return None


class ExportData(_OTreeAsyncJsonWebsocketConsumer):

    '''
    I load tested this locally with sqlite and:
    - large files up to 22MB (by putting long text in LongStringFields)
    - thousands of participants/rounds, 111000 rows and 20 cols in excel file.
    '''

    unrestricted_when = None

    async def post_receive_json(self, content: dict):
        '''
        if an app name is given, export the app.
        otherwise, export all the data (wide).
        don't need time_spent or chat yet, they are quick enough
        '''

        app_name = content.get('app_name')
        is_custom = content.get('is_custom')

        iso_date = datetime.date.today().isoformat()
        with io.StringIO() as fp:
            # Excel requires BOM; otherwise non-english characters are garbled
            if content.get('for_excel'):
                fp.write('\ufeff')
            if app_name:
                if is_custom:
                    fxn = custom_export_app
                else:
                    fxn = export_app
                await database_sync_to_async(fxn)(app_name, fp)
                file_name_prefix = app_name
            else:
                await database_sync_to_async(export_wide)(fp)
                file_name_prefix = 'all_apps_wide'
            data = fp.getvalue()

        file_name = f'{file_name_prefix}_{iso_date}.csv'

        content.update(file_name=file_name, data=data, mime_type='text/csv')
        # this doesn't go through channel layer, so it is probably safer
        # in terms of sending large data
        await self.send_json(content)

    def group_name(self, **kwargs):
        return None


class NoOp(WebsocketConsumer):
    '''keep this in for a few months'''

    pass


def parse_querystring(query_string) -> dict:
    '''it seems parse_qs omits keys with empty values'''
    return {k: v[0] for k, v in urllib.parse.parse_qs(query_string.decode()).items()}


class LifespanApp:
    '''
    temporary shim for https://github.com/django/channels/issues/1216
    needed so that hypercorn doesn't display an error.
    this uses ASGI 2.0 format, not the newer 3.0 single callable
    '''

    def __init__(self, scope):
        self.scope = scope

    async def __call__(self, receive, send):
        if self.scope['type'] == 'lifespan':
            while True:
                message = await receive()
                if message['type'] == 'lifespan.startup':
                    await send({'type': 'lifespan.startup.complete'})
                elif message['type'] == 'lifespan.shutdown':
                    await send({'type': 'lifespan.shutdown.complete'})
                    return
