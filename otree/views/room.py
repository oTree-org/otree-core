import time

import vanilla
from django.urls import reverse
from django.http import HttpResponseRedirect, JsonResponse
from otree.channels import utils as channel_utils
from otree.models_concrete import ParticipantRoomVisit
from otree.room import ROOM_DICT
from otree.views.admin import CreateSession


class Rooms(vanilla.TemplateView):
    template_name = 'otree/admin/Rooms.html'

    url_pattern = r"^rooms/$"

    def get_context_data(self, **kwargs):
        return {'rooms': ROOM_DICT.values()}


class RoomWithoutSession(CreateSession):
    template_name = 'otree/admin/RoomWithoutSession.html'
    room = None

    url_pattern = r"^room_without_session/(?P<room_name>.+)/$"

    def dispatch(self, request, *args, **kwargs):
        self.room = ROOM_DICT[kwargs['room_name']]
        if self.room.has_session():
            return HttpResponseRedirect(
                reverse('RoomWithSession', args=[kwargs['room_name']]))
        return super(RoomWithoutSession, self).dispatch(
            request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = {
            'participant_urls': self.room.get_participant_urls(self.request),
            'room_wide_url': self.room.get_room_wide_url(self.request),
            'room': self.room,
            'collapse_links': True,
        }
        kwargs.update(context)

        return super(RoomWithoutSession, self).get_context_data(**kwargs)

    def socket_url(self):
        return channel_utils.room_admin_path(self.room.name)


class RoomWithSession(vanilla.TemplateView):
    template_name = 'otree/admin/RoomWithSession.html'
    room = None

    url_pattern = r"^room_with_session/(?P<room_name>.+)/$"

    def dispatch(self, request, *args, **kwargs):
        self.room = ROOM_DICT[kwargs['room_name']]
        if not self.room.has_session():
            return HttpResponseRedirect(
                reverse('RoomWithoutSession', args=[kwargs['room_name']]))
        return super(RoomWithSession, self).dispatch(
            request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = {
            'participant_urls': self.room.get_participant_urls(self.request),
            'room_wide_url': self.room.get_room_wide_url(self.request),
            'session_url': reverse(
                'SessionMonitor',
                args=(self.room.get_session().code,)),
            'room': self.room,
            'collapse_links': True,
        }
        kwargs.update(context)

        return super(RoomWithSession, self).get_context_data(**kwargs)


class CloseRoom(vanilla.View):
    url_pattern = r"^CloseRoom/(?P<room_name>.+)/$"

    def post(self, request, *args, **kwargs):
        room_name = kwargs['room_name']
        self.room = ROOM_DICT[room_name]
        self.room.set_session(None)
        # in case any failed to be cleared through regular ws.disconnect
        ParticipantRoomVisit.objects.filter(
            room_name=room_name,
        ).delete()
        return HttpResponseRedirect(
            reverse('RoomWithoutSession', args=[room_name]))


class StaleRoomVisits(vanilla.View):

    url_pattern = r'^StaleRoomVisits/(?P<room>\w+)/$'

    def get(self, request, *args, **kwargs):
        stale_threshold = time.time() - 20
        stale_participant_labels = ParticipantRoomVisit.objects.filter(
            room_name=kwargs['room'],
            last_updated__lt=stale_threshold
        ).values_list('participant_label', flat=True)

        # make json serializable
        stale_participant_labels = list(stale_participant_labels)

        return JsonResponse({'participant_labels': stale_participant_labels})


class ActiveRoomParticipantsCount(vanilla.View):

    url_pattern = r'^ActiveRoomParticipantsCount/(?P<room>\w+)/$'

    def get(self, request, *args, **kwargs):
        count = ParticipantRoomVisit.objects.filter(
            room_name=kwargs['room'],
            last_updated__gte=time.time() - 20
        ).count()

        return JsonResponse({'count': count})