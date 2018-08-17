import json
import logging
import django.db
import django.utils.timezone
import traceback
import time
from channels import Group
from channels.generic.websockets import JsonWebsocketConsumer
from django.core.signing import Signer, BadSignature
import otree.session
from otree.channels.utils import get_chat_group
from otree.models import Participant, Session
from otree.models_concrete import (
    CompletedGroupWaitPage, CompletedSubsessionWaitPage, ChatMessage)
from otree.common_internal import (
    get_models_module
)
import otree.channels.utils as channel_utils
from otree.models_concrete import (
    FailedSessionCreation, ParticipantRoomVisit,
    FAILURE_MESSAGE_MAX_LENGTH, BrowserBotsLauncherSessionCode)
from otree.room import ROOM_DICT
import otree.bots.browser
from otree.export import export_wide, export_app
import io
import base64
import datetime
from django.conf import settings

logger = logging.getLogger(__name__)


class InvalidWebSocketParams(Exception):
    '''exception to raise when websocket params are invalid'''

class OTreeJsonWebsocketConsumer(JsonWebsocketConsumer):
    '''
    THIS IS NOT PUBLIC API.
    Third party apps should not subclass this.
    Either copy this class into your code,
    or subclass directly from JsonWebsocketConsumer,
    '''

    def raw_connect(self, message, **kwargs):
        try:
            super().raw_connect(message, **kwargs)
        except InvalidWebSocketParams:
            logger.warning('Rejected request: {}'.format(self.path))

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

    def connection_groups(self, **kwargs):
        kwargs = self.clean_kwargs(**kwargs)
        group_name = self.group_name(**kwargs)
        return [group_name]

    def connect(self, message, **kwargs):
        # don't send accept: True until we upgrade to channels 1.0+
        # self.message.reply_channel.send({"accept": True})
        # only wrap this for connect. it's not as high-priority for
        # disconnect or receive.
        kwargs = self.clean_kwargs(**kwargs)
        self.post_connect(**kwargs)

    def post_connect(self, **kwargs):
        pass

    def disconnect(self, message, **kwargs):
        kwargs = self.clean_kwargs(**kwargs)
        self.pre_disconnect(**kwargs)

    def pre_disconnect(self, **kwargs):
        pass

    def receive(self, content, **kwargs):
        kwargs = self.clean_kwargs(**kwargs)
        self.post_receive(content, **kwargs)

    def post_receive(self, content, **kwargs):
        pass


class GroupByArrivalTime(OTreeJsonWebsocketConsumer):

    def clean_kwargs(self, params):
        session_pk, page_index, app_name, player_id = params.split(',')
        return {
            'app_name': app_name,
            'session_pk': int(session_pk),
            'page_index': int(page_index),
            'player_id': int(player_id)
        }

    def group_name(self, app_name, player_id, page_index, session_pk):
        gn = channel_utils.gbat_group_name(
            session_pk, page_index)
        return gn

    def post_connect(self, app_name, player_id, page_index, session_pk):
        models_module = get_models_module(app_name)
        group_id_in_subsession = models_module.Group.objects.filter(
            player__id=player_id).values_list(
            'id_in_subsession', flat=True)[0]

        ready = CompletedGroupWaitPage.objects.filter(
            page_index=page_index,
            id_in_subsession=int(group_id_in_subsession),
            session_id=session_pk,
            ).exists()
        if ready:
            self.send({'status': 'ready'})


class WaitPage(OTreeJsonWebsocketConsumer):

    def clean_kwargs(self, params):
        session_pk, page_index, group_id_in_subsession = params.split(',')
        return {
            'session_pk': int(session_pk),
            'page_index': int(page_index),
            # don't convert group_id_in_subsession to int yet, it might be null
            'group_id_in_subsession': group_id_in_subsession,
        }

    def group_name(self, session_pk, page_index, group_id_in_subsession):
        return channel_utils.wait_page_group_name(
                session_pk, page_index, group_id_in_subsession)

    def post_connect(self, session_pk, page_index, group_id_in_subsession):
        # in case message was sent before this web socket connects
        if group_id_in_subsession:
            ready = CompletedGroupWaitPage.objects.filter(
                page_index=page_index,
                id_in_subsession=int(group_id_in_subsession),
                session_id=session_pk,
                ).exists()
        else:  # subsession
            ready = CompletedSubsessionWaitPage.objects.filter(
                page_index=page_index,
                session_id=session_pk,
                ).exists()
        if ready:
            self.send({'status': 'ready'})


class AutoAdvance(OTreeJsonWebsocketConsumer):
    def clean_kwargs(self, params):
        participant_code, page_index = params.split(',')
        return {
            'participant_code': participant_code,
            'page_index': int(page_index),
        }

    def group_name(self, page_index, participant_code):
        return 'auto-advance-{}'.format(participant_code)

    def post_connect(self, page_index, participant_code):
        # in case message was sent before this web socket connects
        result = Participant.objects.filter(
                code=participant_code).values_list(
            '_index_in_pages', flat=True)
        try:
            page_should_be_on = result[0]
        except IndexError:
            # doesn't get shown because not yet localized
            self.send({'error': 'Participant not found in database.'})
            return
        if page_should_be_on > page_index:
            self.send({'auto_advanced': True})


def create_session(message):
    group = Group(message['channels_group_name'])

    kwargs = message['kwargs']

    try:
        session = otree.session.create_session(**kwargs)
        if message['use_browser_bots']:
            otree.bots.browser.initialize_session(
                session_pk=session.pk,
                case_number=None
            )
        session.ready_for_browser = True
        session.save()
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
            pre_create_id=kwargs['pre_create_id'],
            message=error_message[:FAILURE_MESSAGE_MAX_LENGTH],
            traceback=traceback_str
        )
        raise

    group.send(
        {'text': json.dumps(
            {'status': 'ready'})}
    )

    if 'room_name' in kwargs:
        Group(channel_utils.room_participants_group_name(kwargs['room_name'])).send(
            {'text': json.dumps(
                {'status': 'session_ready'})}
        )


class WaitForSession(OTreeJsonWebsocketConsumer):
    def clean_kwargs(self, **kwargs):
        return kwargs

    def group_name(self, pre_create_id):
        return channel_utils.create_session_group_name(pre_create_id)

    def post_connect(self, pre_create_id):

        group_name = self.group_name(pre_create_id)

        # in case message was sent before this web socket connects
        if Session.objects.filter(
                _pre_create_id=pre_create_id, ready_for_browser=True).exists():
            self.group_send(group_name, {'status': 'ready'})
        else:
            failure = FailedSessionCreation.objects.filter(
                pre_create_id=pre_create_id
            ).first()
            if failure:
                self.group_send(group_name,
                        {'error': failure.message,
                         'traceback': failure.traceback})


class RoomAdmin(OTreeJsonWebsocketConsumer):

    def group_name(self, room):
        return 'room-admin-{}'.format(room)

    def post_connect(self, room):

        room_object = ROOM_DICT[room]

        now = time.time()
        stale_threshold = now - 15
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
        very_stale_threshold = now - 10*60
        ParticipantRoomVisit.objects.filter(
            room_name=room_object.name,
            last_updated__lt=very_stale_threshold,
        ).delete()


class RoomParticipant(OTreeJsonWebsocketConsumer):

    def clean_kwargs(self, params):
        room_name, participant_label, tab_unique_id = params.split(',')
        return {
            'room_name': room_name,
            'participant_label': participant_label,
            'tab_unique_id': tab_unique_id,
        }

    def group_name(self, room_name, participant_label, tab_unique_id):
        return channel_utils.room_participants_group_name(room_name)

    def post_connect(self, room_name, participant_label, tab_unique_id):
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
            self.group_send(
                'room-admin-{}'.format(room_name),
                {
                    'status': 'add_participant',
                    'participant': participant_label
                }
            )

    def pre_disconnect(self, room_name, participant_label, tab_unique_id):

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


class BrowserBotsLauncher(OTreeJsonWebsocketConsumer):

    def group_name(self, session_code):
        return channel_utils.browser_bots_launcher_group(session_code)


class BrowserBot(OTreeJsonWebsocketConsumer):

    def group_name(self):
        return 'browser_bot_wait'

    def post_connect(self):
        launcher_session_info = BrowserBotsLauncherSessionCode.objects.first()
        if launcher_session_info:
            self.send({'status': 'session_ready'})


class ChatConsumer(OTreeJsonWebsocketConsumer):

    # Set to True if you want it, else leave it out
    strict_ordering = False

    def clean_kwargs(self, params):

        signer = Signer(sep='/')
        try:
            original_params = signer.unsign(params)
        except BadSignature:
            raise InvalidWebSocketParams

        channel, participant_id = original_params.split('/')

        return {
            'channel': channel,
            'participant_id': int(participant_id),
        }

    def group_name(self, channel, participant_id):
        return get_chat_group(channel)

    def post_connect(self, **kwargs):

        history = ChatMessage.objects.filter(
            channel=kwargs['channel']).order_by('timestamp').values(
                'nickname', 'body', 'participant_id'
        )

        # Convert ValuesQuerySet to list
        self.send(list(history))

    def post_receive(self, content, channel, participant_id):
        content['channel'] = channel
        content['participant_id'] = participant_id

        # in the Channels docs, the example has a separate msg_consumer
        # channel, so this can be done asynchronously.
        # but i think the perf is probably good enough.
        # moving into here for simplicity, especially for testing.
        nickname_signed = content['nickname_signed']
        nickname = Signer().unsign(nickname_signed)
        channel = content['channel']
        channels_group = get_chat_group(channel)

        body = content['body']
        participant_id = content['participant_id']

        chat_message = {
            'nickname': nickname,
            'body': body,
            'participant_id': participant_id
        }

        Group(channels_group).send({'text': json.dumps([chat_message])})

        ChatMessage.objects.create(
            participant_id=participant_id,
            channel=channel,
            body=body,
            nickname=nickname
        )


class ExportData(OTreeJsonWebsocketConsumer):
    # access to self.message.user for auth
    http_user = True

    def post_receive(self, content: dict):
        '''
        if an app name is given, export the app.
        otherwise, export all the data (wide).
        don't need time_spent or chat yet, they are quick enough
        '''

        # authenticate
        # maybe it should be is_superuser or something else more specific
        # but this is to be consistent with the rest of Django's login
        if settings.AUTH_LEVEL and not self.message.user.is_authenticated:
            logger.warning(
                'rejected access to data export through non-authenticated '
                'websocket'
            )
            return

        file_extension = content['file_extension']
        app_name = content.get('app_name')

        if file_extension == 'xlsx':
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            IOClass = io.BytesIO
        else:
            mime_type = 'text/csv'
            IOClass = io.StringIO

        iso_date = datetime.date.today().isoformat()
        with IOClass() as fp:
            if app_name:
                export_app(app_name, fp, file_extension=file_extension)
                file_name_prefix = app_name
            else:
                export_wide(fp, file_extension=file_extension)
                file_name_prefix = 'all_apps_wide'
            data = fp.getvalue()

        file_name = '{}_{}.{}'.format(
            file_name_prefix, iso_date, file_extension)

        if file_extension == 'xlsx':
            data = base64.b64encode(data).decode('utf-8')

        content.update({
            'file_name': file_name,
            'data': data,
            'mime_type': mime_type,
        })
        self.send(content)

    def connection_groups(self, **kwargs):
        return []
