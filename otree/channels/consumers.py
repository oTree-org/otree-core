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

import otree.bots.browser
import otree.channels.utils as channel_utils
import otree.session
from otree.channels.utils import get_chat_group
from otree.common import get_models_module
from otree.export import export_wide, export_app
from otree.models import Participant
from otree.models_concrete import (
    CompletedGroupWaitPage,
    CompletedSubsessionWaitPage,
    ChatMessage,
    WaitPagePassage,
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
            # print(msg)
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

    async def pre_disconnect(self, session_pk, participant_id, **kwargs):

        await create_waitpage_passage(
            participant_id=participant_id, session_pk=session_pk, is_enter=False
        )


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
        await create_waitpage_passage(
            participant_id=participant_id, session_pk=session_pk, is_enter=True
        )


class GroupWaitPage(BaseWaitPage):

    kwarg_names = SubsessionWaitPage.kwarg_names + ('group_id_in_subsession',)

    def group_name(
        self, session_pk, page_index, group_id_in_subsession, participant_id
    ):
        return channel_utils.group_wait_page_name(
            session_pk, page_index, group_id_in_subsession
        )

    def completion_exists(self, **kwargs):
        return CompletedGroupWaitPage.objects.filter(**kwargs).exists()

    async def post_connect(
        self, session_pk, page_index, group_id_in_subsession, participant_id
    ):
        if await database_sync_to_async(self.completion_exists)(
            page_index=page_index,
            id_in_subsession=group_id_in_subsession,
            session_id=session_pk,
        ):
            await self.wait_page_ready()
        await create_waitpage_passage(
            participant_id=participant_id, session_pk=session_pk, is_enter=True
        )


class GroupByArrivalTime(_OTreeAsyncJsonWebsocketConsumer):

    unrestricted_when = ALWAYS_UNRESTRICTED

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

        return CompletedGroupWaitPage.objects.filter(
            page_index=page_index,
            id_in_subsession=int(group_id_in_subsession),
            session_id=session_pk,
        ).exists()

    async def post_connect(
        self, app_name, player_id, page_index, session_pk, participant_id
    ):
        if await database_sync_to_async(self.is_ready)(
            app_name=app_name,
            player_id=player_id,
            page_index=page_index,
            session_pk=session_pk,
        ):
            await self.gbat_ready()
        await create_waitpage_passage(
            participant_id=participant_id, session_pk=session_pk, is_enter=True
        )

    async def gbat_ready(self, event=None):
        await self.send_json({'status': 'ready'})

    async def pre_disconnect(
        self, app_name, player_id, page_index, session_pk, participant_id
    ):
        await create_waitpage_passage(
            participant_id=participant_id, session_pk=session_pk, is_enter=False
        )


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
            session = await database_sync_to_async(otree.session.create_session)(
                **session_kwargs
            )
            if use_browser_bots:
                await database_sync_to_async(otree.bots.browser.initialize_session)(
                    session_pk=session.pk, case_number=None
                )
        except Exception as e:

            # full error message is printed to console (though sometimes not?)
            error_message = 'Failed to create session: "{}"'.format(e)
            traceback_str = traceback.format_exc()
            await self.send_response_to_browser(
                dict(error=error_message, traceback=traceback_str)
            )
            raise

        session_home_view = (
            'MTurkCreateHIT' if session.is_mturk() else 'SessionStartLinks'
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

        edited_session_config_fields = {}

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
                    edited_session_config_fields[field] = new_value
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
                        edited_session_config_fields[field] = new_value

        use_browser_bots = edited_session_config_fields.get(
            'use_browser_bots', config.get('use_browser_bots', False)
        )

        # if room_name is missing, it will be empty string
        room_name = form.cleaned_data['room_name'] or None

        await self.create_session_then_send_start_link(
            session_config_name=session_config_name,
            num_participants=num_participants,
            is_demo=False,
            is_mturk=is_mturk,
            edited_session_config_fields=edited_session_config_fields,
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
        del event['type']
        await self.send_json(event)


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


class ExportData(_OTreeAsyncJsonWebsocketConsumer):

    '''
    I load tested this locally with sqlite/redis and:
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

        file_extension = content['file_extension']
        app_name = content.get('app_name')

        if file_extension == 'xlsx':
            mime_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            IOClass = io.BytesIO
        else:
            mime_type = 'text/csv'
            IOClass = io.StringIO

        iso_date = datetime.date.today().isoformat()
        with IOClass() as fp:
            if app_name:
                await database_sync_to_async(export_app)(
                    app_name, fp, file_extension=file_extension
                )
                file_name_prefix = app_name
            else:
                await database_sync_to_async(export_wide)(
                    fp, file_extension=file_extension
                )
                file_name_prefix = 'all_apps_wide'
            data = fp.getvalue()

        file_name = f'{file_name_prefix}_{iso_date}.{file_extension}'

        if file_extension == 'xlsx':
            data = base64.b64encode(data).decode('utf-8')

        content.update(file_name=file_name, data=data, mime_type=mime_type)
        # this doesn't go through channel layer, so it is probably safer
        # in terms of sending large data
        await self.send_json(content)

    def group_name(self, **kwargs):
        return None


class NoOp(WebsocketConsumer):
    pass


def parse_querystring(query_string) -> dict:
    '''it seems parse_qs omits keys with empty values'''
    return {k: v[0] for k, v in urllib.parse.parse_qs(query_string.decode()).items()}


async def create_waitpage_passage(*, participant_id, session_pk, is_enter):
    await database_sync_to_async(_create_waitpage_passage)(
        participant_id=participant_id, session_pk=session_pk, is_enter=is_enter
    )


def _create_waitpage_passage(*, participant_id, session_pk, is_enter):
    '''if the session was deleted, this would raise'''
    try:
        WaitPagePassage.objects.create(
            participant_id=participant_id,
            session_id=session_pk,
            is_enter=is_enter,
            epoch_time=time.time(),
        )
    except:
        pass
