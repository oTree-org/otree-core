import otree.views.cbv

from otree.channels import utils as channel_utils
from otree.room import ROOM_DICT, BaseRoom
from otree.session import SESSION_CONFIGS_DICT
from otree.views.admin import CreateSessionForm
from .cbv import AdminView


class Rooms(AdminView):
    url_pattern = '/rooms'

    def vars_for_template(self):
        from threading import get_ident
        return {'rooms': ROOM_DICT.values()}


class RoomWithoutSession(AdminView):
    room: BaseRoom
    form_class = CreateSessionForm

    url_pattern = '/room_without_session/{room_name}'

    def intercept_dispatch(self, room_name):
        self.room_name = room_name
        self.room = ROOM_DICT[room_name]
        if self.room.has_session():
            return self.redirect('RoomWithSession', room_name=room_name)

    def get_form(self):
        return CreateSessionForm(data=dict(room_name=self.room_name))

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            configs=SESSION_CONFIGS_DICT.values(),
            participant_urls=self.room.get_participant_urls(self.request),
            room_wide_url=self.room.get_room_wide_url(self.request),
            room=self.room,
            collapse_links=True,
            **kwargs
        )

    def socket_url(self):
        return channel_utils.room_admin_path(self.room.name)


class RoomWithSession(AdminView):
    template_name = 'otree/RoomWithSession.html'
    room = None

    url_pattern = '/room_with_session/{room_name}'

    def intercept_dispatch(self, room_name):
        self.room = ROOM_DICT[room_name]
        if not self.room.has_session():
            return self.redirect('RoomWithoutSession', room_name=room_name)

    def get_context_data(self, **kwargs):
        from otree.asgi import reverse

        session_code = self.room.get_session().code
        return super().get_context_data(
            participant_urls=self.room.get_participant_urls(self.request),
            room_wide_url=self.room.get_room_wide_url(self.request),
            session_url=reverse('SessionMonitor', code=session_code),
            room=self.room,
            collapse_links=True,
            **kwargs
        )


class CloseRoom(AdminView):
    url_pattern = '/CloseRoom/{room_name}'

    def post(self, request, room_name):
        self.room = ROOM_DICT[room_name]
        self.room.set_session(None)
        return self.redirect('RoomWithoutSession', room_name=room_name)
