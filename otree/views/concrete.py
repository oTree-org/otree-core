#!/usr/bin/env python
# -*- coding: utf-8 -*-


# =============================================================================
# IMPORTS
# =============================================================================

import time

import django.utils.timezone
from django.core.urlresolvers import reverse
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.contrib import messages
from django.http import (
    HttpResponse, HttpResponseRedirect, HttpResponseNotFound
)
from django.utils.translation import ugettext as _

import vanilla

from boto.mturk.connection import MTurkRequestError

import otree.constants_internal as constants
import otree.models.session
from otree.models.participant import Participant
from otree.common_internal import lock_on_this_code_path, make_hash
import otree.views.admin
from otree.views.mturk import MTurkConnection
import otree.common_internal
from otree.views.abstract import (
    NonSequenceUrlMixin, OTreeMixin,

    NO_PARTICIPANTS_LEFT_MSG
)
from otree.models_concrete import GroupSize  # noqa
from otree.room import ROOM_DICT


class OutOfRangeNotification(NonSequenceUrlMixin, OTreeMixin, vanilla.View):
    name_in_url = 'shared'

    def dispatch(self, request, *args, **kwargs):
        return TemplateResponse(
            request, 'otree/OutOfRangeNotification.html'
        )


class InitializeParticipant(vanilla.UpdateView):
    """just collects data and sets properties. not essential to functionality.
    the only exception is if the participant needs to be assigned to groups on
    the fly, which is done here.

    2014-11-16: also, this sets _last_page_timestamp. what if that is not set?
    will it still work?

    """

    @classmethod
    def url_pattern(cls):
        return r'^InitializeParticipant/(?P<{}>[a-z0-9]+)/$'.format(
            constants.participant_code
        )

    def get(self, *args, **kwargs):

        participant = get_object_or_404(
            Participant,
            code=kwargs[constants.participant_code]
        )

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

    @classmethod
    def url_pattern(cls):
        return r"^MTurkLandingPage/(?P<session_code>[a-z0-9]+)/$"

    @classmethod
    def url_name(cls):
        return 'mturk_landing_page'

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
            url_start = reverse('mturk_start', args=(self.session.code,))
            url_start = otree.common_internal.add_params_to_url(url_start, {
                'assignmentId': self.request.GET['assignmentId'],
                'workerId': self.request.GET['workerId']})
            return HttpResponseRedirect(url_start)
        else:
            context = super(MTurkLandingPage, self).get_context_data(**kwargs)
            return self.render_to_response(context)


class MTurkStart(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^MTurkStart/(?P<session_code>[a-z0-9]+)/$"

    @classmethod
    def url_name(cls):
        return 'mturk_start'

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
        if self.session.mturk_qualification_type_id:
            with MTurkConnection(
                self.request, self.session.mturk_sandbox
            ) as mturk_connection:
                try:
                    mturk_connection.assign_qualification(
                        self.session.mturk_qualification_type_id,
                        worker_id
                    )
                except MTurkRequestError as e:
                    if (
                        e.error_code ==
                        'AWS.MechanicalTurk.QualificationAlreadyExists'
                    ):
                        pass
                    else:
                        raise
        try:
            participant = self.session.participant_set.get(
                mturk_worker_id=worker_id,
                mturk_assignment_id=assignment_id)
        except Participant.DoesNotExist:
            with lock_on_this_code_path():
                try:
                    participant = (
                        Participant.objects.select_for_update().filter(
                            session=self.session,
                            visited=False
                        )
                    ).order_by('start_order')[0]
                except IndexError:
                    return HttpResponseNotFound(NO_PARTICIPANTS_LEFT_MSG)

            # 2014-10-17: needs to be here even if it's also set in
            # the next view to prevent race conditions
            participant.visited = True
            participant.mturk_worker_id = worker_id
            participant.mturk_assignment_id = assignment_id
            participant.save()
        return HttpResponseRedirect(participant._start_url())


class JoinSessionAnonymously(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^join/(?P<anonymous_code>[a-z0-9]+)/$'

    @classmethod
    def url_name(cls):
        return 'join_session_anonymously'

    def get(self, *args, **kwargs):

        anonymous_code = kwargs['anonymous_code']
        session = get_object_or_404(
            otree.models.Session, _anonymous_code=anonymous_code
        )
        with lock_on_this_code_path():
            try:
                participant = (
                    Participant.objects.select_for_update().filter(
                        session=session,
                        visited=False
                    )
                ).order_by('start_order')[0]
            except IndexError:
                return HttpResponseNotFound(NO_PARTICIPANTS_LEFT_MSG)

            # 2014-10-17: needs to be here even if it's also set in
            # the next view to prevent race conditions
            participant.visited = True
            participant.label = (
                self.request.GET.get('participant_label') or participant.label
            )
            participant.save()
        return HttpResponseRedirect(participant._start_url())


class AssignVisitorToRoom(vanilla.TemplateView):
    template_name = "otree/InputParticipantLabel.html"

    @classmethod
    def url_name(cls):
        return 'assign_visitor_to_room'

    @classmethod
    def url_pattern(cls):
        return r'^{}/$'.format(cls.__name__)

    def get(self, *args, **kwargs):

        room_name = self.request.GET.get(
            'room'
        )
        try:
            room = ROOM_DICT[room_name]
        except KeyError:
            return HttpResponseNotFound('Invalid room specified in url')

        participant_label = self.request.GET.get(
            'participant_label'
        )
        if room.has_participant_labels():
            if not participant_label:
                if not room.use_secure_urls:
                    return super(AssignVisitorToRoom, self).get(args, kwargs)

            if participant_label not in room.get_participant_labels():
                return HttpResponseNotFound('Participant is not expected in this room. Please contact the session supervisor.')

            if room.use_secure_urls:
                hash = self.request.GET.get('hash')
                if hash != make_hash(participant_label):
                    return HttpResponseNotFound('Invalid hash parameter.')

        session = room.session
        if session is None:
            return HttpResponse('No session in room. Refresh the page.')

        assign_new = not room.has_participant_labels()
        if not assign_new:
            try:
                participant = Participant.objects.get(
                    session=session,
                    label=participant_label
                )
            except Participant.DoesNotExist:
                assign_new = True

        if assign_new:
            with lock_on_this_code_path():
                try:
                    participant = (
                        Participant.objects.select_for_update().filter(
                            session=session,
                            visited=False)
                    ).order_by('start_order')[0]
                except IndexError:
                    return HttpResponseNotFound(NO_PARTICIPANTS_LEFT_MSG)

                participant.label = participant_label
                # 2014-10-17: needs to be here even if it's also set in
                # the next view to prevent race conditions
                participant.visited = True
                participant.save()

        return HttpResponseRedirect(participant._start_url())

    def get_context_data(self, **kwargs):
        return {'room': self.request.GET.get('room')}

class AdvanceSession(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^AdvanceSession/(?P<{}>[0-9]+)/$'.format('session_pk')

    @classmethod
    def url_name(cls):
        return 'session_advance'

    @classmethod
    def url(cls, session):
        return '/AdvanceSession/{}/'.format(session.pk)

    def dispatch(self, request, *args, **kwargs):
        self.session = get_object_or_404(
            otree.models.session.Session, pk=kwargs['session_pk']
        )
        return super(AdvanceSession, self).dispatch(
            request, *args, **kwargs
        )

    def get(self, request, *args, **kwargs):
        self.session.advance_last_place_participants()
        redirect_url = reverse('session_monitor', args=(self.session.pk,))
        return HttpResponseRedirect(redirect_url)


class ToggleArchivedSessions(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^ToggleArchivedSessions/'

    @classmethod
    def url_name(cls):
        return 'toggle_archived_sessions'

    def post(self, request, *args, **kwargs):
        for pk in request.POST.getlist('item-action'):
            session = get_object_or_404(
                otree.models.session.Session, pk=pk
            )
            if session.archived:
                session.archived = False
            else:
                session.archived = True
            session.save()
        return HttpResponseRedirect(request.POST['origin_url'])


class DeleteSessions(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^DeleteSessions/'

    @classmethod
    def url_name(cls):
        return 'delete_sessions'

    def post(self, request, *args, **kwargs):
        for pk in request.POST.getlist('item-action'):
            session = get_object_or_404(
                otree.models.session.Session, pk=pk
            )
            session.delete()
        return HttpResponseRedirect(reverse('sessions'))
