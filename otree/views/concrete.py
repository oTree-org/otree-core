#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================

import time

from datetime import timedelta

import django.utils.timezone
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render_to_response
from django.template.response import TemplateResponse
from django.http import (
    HttpResponse, HttpResponseRedirect,
    HttpResponseNotFound, Http404, JsonResponse
)
from django.utils.translation import ugettext as _

import vanilla

import otree.constants_internal as constants
import otree.models
from otree.models import Participant, Session
from otree.common_internal import make_hash, add_params_to_url, get_redis_conn
import otree.views.admin
import otree.views.mturk
import otree.common_internal
from otree.views.abstract import (
    GenericWaitPageMixin,
    global_lock, NO_PARTICIPANTS_LEFT_MSG)
from otree.room import ROOM_DICT
from otree.models_concrete import (
    ParticipantRoomVisit, BrowserBotsLauncherSessionCode)


class OutOfRangeNotification(vanilla.View):
    name_in_url = 'shared'

    def dispatch(self, request, *args, **kwargs):
        return TemplateResponse(
            request, 'otree/OutOfRangeNotification.html'
        )

    url_pattern = '^OutOfRangeNotification/$'


class InitializeParticipant(vanilla.UpdateView):
    """just collects data and sets properties. not essential to functionality.
    the only exception is if the participant needs to be assigned to groups on
    the fly, which is done here.

    2014-11-16: also, this sets _last_page_timestamp. what if that is not set?
    will it still work?

    """

    url_pattern = r'^InitializeParticipant/(?P<{}>[a-z0-9]+)/$'.format(
            constants.participant_code
        )

    def get(self, *args, **kwargs):

        participant = get_object_or_404(
            Participant,
            code=kwargs[constants.participant_code]
        )

        if participant._index_in_pages == 0:
            participant._index_in_pages = 1
            participant.visited = True

            # participant.label might already have been set
            participant.label = participant.label or self.request.GET.get(
                constants.participant_label
            )
            participant.ip_address = self.request.META['REMOTE_ADDR']

            now = django.utils.timezone.now()
            participant.time_started = now
            participant._last_page_timestamp = time.time()

            participant.save()
        first_url = participant._url_i_should_be_on()
        return HttpResponseRedirect(first_url)


class MTurkLandingPage(vanilla.TemplateView):

    def get_template_names(self):
        hit_settings = self.session.config['mturk_hit_settings']
        return [hit_settings['preview_template']]

    url_pattern = r"^MTurkLandingPage/(?P<session_code>[a-z0-9]+)/$"

    def dispatch(self, request, *args, **kwargs):
        session_code = kwargs['session_code']
        self.session = get_object_or_404(
            otree.models.Session, code=session_code
        )
        return super(MTurkLandingPage, self).dispatch(
            request, *args, **kwargs
        )

    def get(self, request, *args, **kwargs):
        assignment_id = (
            self.request.GET['assignmentId']
            if 'assignmentId' in self.request.GET else
            ''
        )
        if assignment_id and assignment_id != 'ASSIGNMENT_ID_NOT_AVAILABLE':
            url_start = reverse('MTurkStart', args=(self.session.code,))
            url_start = add_params_to_url(url_start, {
                'assignmentId': self.request.GET['assignmentId'],
                'workerId': self.request.GET['workerId']})
            return HttpResponseRedirect(url_start)

        context = super(MTurkLandingPage, self).get_context_data(**kwargs)
        return self.render_to_response(context)


class MTurkStart(vanilla.View):

    url_pattern = r"^MTurkStart/(?P<session_code>[a-z0-9]+)/$"

    def dispatch(self, request, *args, **kwargs):
        session_code = kwargs['session_code']
        self.session = get_object_or_404(
            otree.models.Session, code=session_code
        )
        return super(MTurkStart, self).dispatch(
            request, *args, **kwargs
        )

    def get(self, *args, **kwargs):
        assignment_id = self.request.GET['assignmentId']
        worker_id = self.request.GET['workerId']
        qualification_id = self.session.config['mturk_hit_settings'].get('grant_qualification_id')
        if qualification_id:
            # don't pass request arg, because we don't want to show a message.
            # using the fully qualified name because that seems to make mock.patch work
            mturk_client = otree.views.mturk.get_mturk_client(
                use_sandbox=self.session.mturk_use_sandbox)
            # seems OK to assign this multiple times
            mturk_client.associate_qualification_with_worker(
                QualificationTypeId=qualification_id,
                WorkerId=worker_id,
                # Mturk complains if I omit IntegerValue
                IntegerValue=1
            )
        try:
            # just check if this worker already game, but
            # don't filter for assignment, because maybe they already started
            # and returned the previous assignment
            # in this case, we should assign back to the same participant
            # so that we don't get duplicates in the DB, and so people
            # can't snoop and try the HIT first, then re-try to get a bigger bonus
            participant = self.session.participant_set.get(
                mturk_worker_id=worker_id)
        except Participant.DoesNotExist:
            with global_lock():
                try:
                    participant = self.session.get_participants().filter(
                        visited=False
                    ).order_by('start_order')[0]
                except IndexError:
                    return HttpResponseNotFound(NO_PARTICIPANTS_LEFT_MSG)

                # 2014-10-17: needs to be here even if it's also set in
                # the next view to prevent race conditions
                # this needs to be inside the lock
                participant.visited = True
                participant.mturk_worker_id = worker_id
        # reassign assignment_id, even if they are returning, because maybe they accepted
        # and then returned, then re-accepted with a different assignment ID
        # if it's their second time
        participant.mturk_assignment_id = assignment_id
        participant.save()
        return HttpResponseRedirect(participant._start_url())


def get_existing_or_new_participant(session, label):
    if label:
        try:
            return session.participant_set.get(label=label)
        except Participant.DoesNotExist:
            pass
    return session.participant_set.filter(
        visited=False).order_by('start_order').first()


def get_participant_with_cookie_check(session, cookies):
    cookie_name = 'session_{}_participant'.format(session.code)
    participant_code = cookies.get(cookie_name)
    # this could return None
    if participant_code:
        return Participant.objects.filter(code=participant_code).first()
    participant = session.participant_set.filter(
        visited=False).order_by('start_order').first()
    if participant:
        cookies[cookie_name] = participant.code
        return participant


def participant_start_page_or_404(session, label, cookies=None):
    '''pass request.session as an arg if you want to get/set a cookie'''
    with global_lock():
        if label:
            participant = get_existing_or_new_participant(session, label)
        elif cookies:
            participant = get_participant_with_cookie_check(session, cookies)
        else:
            # this repeats the first 'if', but simpler to write it this way
            participant = get_existing_or_new_participant(session, label)
        if not participant:
            return HttpResponseNotFound(NO_PARTICIPANTS_LEFT_MSG)

        # needs to be here even if it's also set in
        # the next view to prevent race conditions
        participant.visited = True
        if label:
            participant.label = label
        participant.save()

    return HttpResponseRedirect(participant._start_url())


class JoinSessionAnonymously(vanilla.View):

    url_pattern = r'^join/(?P<anonymous_code>[a-z0-9]+)/$'

    def get(self, *args, **kwargs):

        anonymous_code = kwargs['anonymous_code']
        session = get_object_or_404(
            otree.models.Session, _anonymous_code=anonymous_code
        )
        label = self.request.GET.get('participant_label')
        return participant_start_page_or_404(session, label)


class AssignVisitorToRoom(GenericWaitPageMixin, vanilla.View):

    url_pattern = r'^room/(?P<room>\w+)/$'

    def dispatch(self, request, *args, **kwargs):
        self.room_name = kwargs['room']
        try:
            room = ROOM_DICT[self.room_name]
        except KeyError:
            return HttpResponseNotFound('Invalid room specified in url')

        self.uses_pin = room.has_pin_code()

        label = self.request.GET.get(
            'participant_label', ''
        )

        if room.has_participant_labels():
            if not label:
                if not room.use_secure_urls:
                    return render_to_response("otree/RoomInputLabel.html")

            if not label in room.get_participant_labels():
                return HttpResponseNotFound(
                    _('Invalid participant label.')
                )

            if room.use_secure_urls:
                hash = self.request.GET.get('hash')
                if hash != make_hash(label):
                    return HttpResponseNotFound('Invalid hash parameter.')

        if self.uses_pin:
            pin_code = self.request.GET.get('pin')
            if not pin_code:
                return super(AssignVisitorToRoom, self).get(args, kwargs)

            if pin_code != room.get_pin_code():
                return HttpResponseNotFound('The given pin code is incorrect.')

        session = room.session
        if session is None:
            self.tab_unique_id = otree.common_internal.random_chars_10()
            self._socket_url_params = ','.join([
                self.room_name,
                label,
                # random chars in case the participant has multiple tabs open
                self.tab_unique_id,
            ])
            return render_to_response(
                "otree/WaitPageRoom.html",
                {
                    'view': self, 'title_text': _('Please wait'),
                    'body_text': _('Waiting for your session to begin')
                }
            )

        if room.has_participant_labels() or label:
            cookies = None
        else:
            cookies = request.session


        # 2017-08-02: changing the behavior so that even in a room without
        # participant_label_file, 2 requests for the same start URL with same label
        # will return the same participant. Not sure if the previous behavior
        # (assigning to 2 different participants) was intentional or bug.
        return participant_start_page_or_404(session, label, cookies)

    def get_context_data(self, **kwargs):
        return {
            'room': self.room_name,
            'uses_pin': self.uses_pin,
        }

    def socket_url(self):
        return '/wait_for_session_in_room/{}/'.format(
            self._socket_url_params
        )

    def redirect_url(self):
        return self.request.get_full_path()


class StaleRoomVisits(vanilla.View):

    url_pattern = r'^StaleRoomVisits/(?P<room>\w+)/$'

    def get(self, request, *args, **kwargs):

        now = django.utils.timezone.now()

        stale_threshold = now - timedelta(seconds=20)
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
        time_threshold = django.utils.timezone.now() - timedelta(seconds=20)
        count = ParticipantRoomVisit.objects.filter(
            room_name=kwargs['room'],
            last_updated__gte=time_threshold
        ).count()

        return JsonResponse({'count': count})


class ParticipantRoomHeartbeat(vanilla.View):

    url_pattern = r'^ParticipantRoomHeartbeat/(?P<tab_unique_id>\w+)/$'

    def get(self, request, *args, **kwargs):
        visit = get_object_or_404(
            ParticipantRoomVisit, tab_unique_id=kwargs['tab_unique_id']
        )
        visit.save()  # save just to update auto_now timestamp
        return HttpResponse('')


class ParticipantHeartbeatGBAT(vanilla.View):
    url_pattern = r'^ParticipantHeartbeatGBAT/(?P<participant_code>\w+)/$'

    def get(self, request, *args, **kwargs):
        Participant.objects.filter(code=kwargs['participant_code']).update(
            _last_request_timestamp=time.time())
        return HttpResponse('')


class AdvanceSession(vanilla.View):

    url_pattern = r'^AdvanceSession/(?P<session_code>[a-z0-9]+)/$'

    # TODO: get rid of this
    @classmethod
    def url(cls, session):
        return '/AdvanceSession/{}/'.format(session.code)

    def dispatch(self, request, *args, **kwargs):
        self.session = get_object_or_404(
            otree.models.Session, code=kwargs['session_code']
        )
        return super(AdvanceSession, self).dispatch(
            request, *args, **kwargs
        )

    # FIXME: this should be POST, not GET
    def get(self, request, *args, **kwargs):
        self.session.advance_last_place_participants()
        redirect_url = reverse('SessionMonitor', args=(self.session.code,))
        return HttpResponseRedirect(redirect_url)


class ToggleArchivedSessions(vanilla.View):

    url_pattern = r'^ToggleArchivedSessions/'

    def post(self, request, *args, **kwargs):
        code_list = request.POST.getlist('item-action')
        sessions = otree.models.Session.objects.filter(
            code__in=code_list)
        code_dict = {True: [], False: []}
        for code, archived in sessions.values_list('code', 'archived'):
            code_dict[archived].append(code)

        for code in code_list:
            if not (code in code_dict[True] or code in code_dict[False]):
                raise Http404('No session with the code %s.' % code)

        # TODO: When `F` implements a toggle, use this instead:
        #       sessions.update(archived=~F('archived'))
        otree.models.Session.objects.filter(
            code__in=code_dict[True]).update(archived=False)
        otree.models.Session.objects.filter(
            code__in=code_dict[False]).update(archived=True)

        return HttpResponseRedirect(request.POST['origin_url'])


class DeleteSessions(vanilla.View):

    url_pattern = r'^DeleteSessions/'

    def dispatch(self, *args, **kwargs):
        return super(DeleteSessions, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        for code in request.POST.getlist('item-action'):
            session = get_object_or_404(
                otree.models.Session, code=code
            )
            session.delete()
        return HttpResponseRedirect(reverse('Sessions'))


class BrowserBotStartLink(GenericWaitPageMixin, vanilla.View):

    url_pattern = r'^browser_bot_start/$'

    def dispatch(self, request, *args, **kwargs):
        get_redis_conn()
        session_info = BrowserBotsLauncherSessionCode.objects.first()
        if session_info:
            session = Session.objects.get(code=session_info.code)
            with global_lock():
                participant = session.get_participants().filter(
                    visited=False).order_by('start_order').first()
                if not participant:
                    return HttpResponseNotFound(NO_PARTICIPANTS_LEFT_MSG)

                # 2014-10-17: needs to be here even if it's also set in
                # the next view to prevent race conditions
                participant.visited = True
                participant.save()

            return HttpResponseRedirect(participant._start_url())
        else:
            ctx = {'view': self, 'title_text': 'Please wait',
                   'body_text': 'Waiting for browser bots session to begin'}
            return render_to_response("otree/WaitPage.html", ctx)

    def socket_url(self):
        return '/browser_bot_wait/'

    def redirect_url(self):
        return self.request.get_full_path()
