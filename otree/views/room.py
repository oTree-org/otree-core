import time

import vanilla
from django.contrib.auth.models import User
from django.urls import reverse, reverse_lazy, path
from django.http import HttpResponseRedirect, JsonResponse
from django.views.generic.edit import FormMixin, ModelFormMixin

from otree import views
from otree.channels import utils as channel_utils
from otree.models_concrete import ParticipantRoomVisit, RoomsTest
from otree.room import ROOM_DICT
from otree.views.admin import CreateSessionForm, CreateRoomForm
from django.shortcuts import redirect, render, get_object_or_404
from otree.session import SESSION_CONFIGS_DICT

## TODO - CREATE LISTVIEW FOR "MINE RUM"


class CreateRoom(vanilla.CreateView):
    template_name = 'otree/admin/CreateRoom.html'
    model = RoomsTest
    form_class = CreateRoomForm
    queryset = RoomsTest.objects.all()

    def get_context_data(self, **kwargs):
        context = super(CreateRoom, self).get_context_data(**kwargs)
        context["teacher"] = User.objects.get(username=self.request.user)
        return context

    def form_valid(self, form):
        form.instance.teacher = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("view_room_with_pk", kwargs={'id': self.object.id})


class RoomDetailView(vanilla.DetailView):
    template_name = "otree/admin/RoomDetail.html"

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(RoomsTest, id=id_)


# This class Rooms, doesthe same as making a listView of all the rooms but not per teacher as this is defined in settings.py
class Rooms(vanilla.TemplateView):
    template_name = 'otree/admin/Rooms.html'
    url_pattern = r"^rooms/$"

    def get_context_data(self, **kwargs):
        return {'rooms': ROOM_DICT.values()}


class RoomWithoutSession(vanilla.TemplateView):
    '''similar to CreateSession view'''

    template_name = 'otree/admin/RoomWithoutSession.html'
    room = None

    url_pattern = r"^room_without_session/(?P<room_name>.+)/$"

    def dispatch(self, request, room_name):
        self.room_name = room_name
        self.room = ROOM_DICT[room_name]
        if self.room.has_session():
            return redirect('RoomWithSession', room_name)
        return super().dispatch(request)

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            configs=SESSION_CONFIGS_DICT.values(),
            participant_urls=self.room.get_participant_urls(self.request),
            room_wide_url=self.room.get_room_wide_url(self.request),
            room=self.room,
            form=CreateSessionForm(room_name=self.room_name),
            collapse_links=True,
            **kwargs
        )

    def socket_url(self):
        return channel_utils.room_admin_path(self.room.name)


class RoomWithSession(vanilla.TemplateView):
    template_name = 'otree/admin/RoomWithSession.html'
    room = None

    url_pattern = r"^room_with_session/(?P<room_name>.+)/$"

    def dispatch(self, request, room_name):
        self.room = ROOM_DICT[room_name]
        if not self.room.has_session():
            return redirect('RoomWithoutSession', room_name)
        return super().dispatch(request)

    def get_context_data(self, **kwargs):
        session_code = self.room.get_session().code
        return super().get_context_data(
            participant_urls=self.room.get_participant_urls(self.request),
            room_wide_url=self.room.get_room_wide_url(self.request),
            session_url=reverse('SessionMonitor', args=[session_code]),
            room=self.room,
            collapse_links=True,
            **kwargs
        )


class CloseRoom(vanilla.View):
    url_pattern = r"^CloseRoom/(?P<room_name>.+)/$"

    def post(self, request, room_name):
        self.room = ROOM_DICT[room_name]
        self.room.set_session(None)
        # in case any failed to be cleared through regular ws.disconnect
        ParticipantRoomVisit.objects.filter(room_name=room_name).delete()
        return redirect('RoomWithoutSession', room_name)


class StaleRoomVisits(vanilla.View):
    url_pattern = r'^StaleRoomVisits/(?P<room>\w+)/$'

    def get(self, request, room):
        stale_threshold = time.time() - 20
        stale_participant_labels = ParticipantRoomVisit.objects.filter(
            room_name=room, last_updated__lt=stale_threshold
        ).values_list('participant_label', flat=True)

        # make json serializable
        stale_participant_labels = list(stale_participant_labels)

        return JsonResponse({'participant_labels': stale_participant_labels})


class ActiveRoomParticipantsCount(vanilla.View):
    url_pattern = r'^ActiveRoomParticipantsCount/(?P<room>\w+)/$'

    def get(self, request, room):
        count = ParticipantRoomVisit.objects.filter(
            room_name=room, last_updated__gte=time.time() - 20
        ).count()

        return JsonResponse({'count': count})
