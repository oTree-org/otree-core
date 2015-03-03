#!/usr/bin/env python
# encoding: utf-8

import urlparse
import vanilla
import boto.mturk.connection
from boto.mturk.connection import MTurkRequestError

from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404

import otree


class MTurkError(Exception):
    def __init__(self, request, message):
        self.message = message
        messages.error(request, message, extra_tags='safe')

    def __str__(self):
        return self.message


class MTurkConnection(boto.mturk.connection.MTurkConnection):

    def __init__(self, request):
        self.request = request

    def __enter__(self):
        if settings.DEBUG:
            mturk_host = settings.MTURK_SANDBOX_HOST
        else:
            mturk_host = settings.MTURK_HOST

        self = boto.mturk.connection.MTurkConnection(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            host=mturk_host,
        )
        return self

    def __exit__(self, exc_type, value, traceback):
        # TODO: need to take care of possible errors (login,
        # "service not approved")
        if exc_type is MTurkRequestError:
            MTurkError(self.request, value.message)
        return True


class CreateHitFromSession(vanilla.View):
    '''
        This view creates mturk HIT for session provided in request
        AWS externalQuestion API is used to generate HIT.
    '''

    @classmethod
    def url_pattern(cls):
        return r'^CreateHitFromSession/(?P<{}>[0-9]+)/$'.format('session_pk')

    @classmethod
    def url_name(cls):
        return 'create_hit_from_session'

    @classmethod
    def url(cls, session):
        return '/CreateHitFromSession/{}/'.format(session.pk)

    def dispatch(self, request, *args, **kwargs):
        self.session = get_object_or_404(
            otree.models.session.Session, pk=kwargs['session_pk']
        )
        return super(CreateHitFromSession, self).dispatch(
            request, *args, **kwargs
        )

    def get(self, request, *args, **kwargs):
        session = self.session
        if session.mturk_HITId:
            return HttpResponseRedirect(reverse('admin_home'))
        with MTurkConnection(self.request) as mturk_connection:
            url_landing_page = self.request.build_absolute_uri(reverse('mturk_landing_page', args=(session.code,)))
            # updating schema from http to https
            # this is compulsory for MTurk exteranlQuestion
            secured_url_landing_page = urlparse.urlunparse(urlparse.urlparse(url_landing_page)._replace(scheme='https'))
            # TODO: validate, that the server support https (heroku does support by default)
            hit_settings = session.session_type['mturk_hit_settings']
            # TODO: validate that there is enought money for the hit
            reward = boto.mturk.price.Price(amount=request.GET['hit-reward'])
            # creating external questions, that would be passed to the hit
            external_question = boto.mturk.question.ExternalQuestion(
                secured_url_landing_page,
                hit_settings['frame_height']
            )
            hit = mturk_connection.create_hit(
                title=request.GET['hit-title'],
                description=request.GET['hit-description'],
                keywords=[k.strip() for k in request.GET['hit-keywords'].split(',')],
                question=external_question,
                max_assignments=len(session.get_participants()),
                reward=reward,
                response_groups=('Minimal', 'HITDetail'),
            )
            session.mturk_HITId = hit[0].HITId
            session.mturk_HITGroupId = hit[0].HITGroupId
            session.save()
            message = """
                You have created a hit for session <strong>%s</strong>.<br>
                To look at the hit as a <em>requester</em>
                follow this <a href="%s" target="_blank">link</a>.<br>
                To look at the hit as a <em>worker</em>
                follow this <a href="%s" target="_blank">link</a>.
                """ % (session.code,
                       session.mturk_requester_url(),
                       session.mturk_worker_url())

            messages.success(request, message, extra_tags='safe')
        return HttpResponseRedirect(reverse('admin_home'))


class PayMTurk(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^PayMTurk/(?P<{}>[0-9]+)/$'.format('session_pk')

    @classmethod
    def url_name(cls):
        return 'pay_mturk'

    @classmethod
    def url(cls, session):
        return '/PayMTurk/{}/'.format(session.pk)

    def post(self, request, *args, **kwargs):
        session = get_object_or_404(
            otree.models.session.Session, pk=kwargs['session_pk']
        )
        participants = session.participant_set.exclude(mturk_assignment_id__isnull=True).\
                                               exclude(mturk_assignment_id="")
        with MTurkConnection(self.request) as mturk_connection:
            participants_reward = [participants.get(mturk_assignment_id=assignment_id)
                                   for assignment_id in request.POST.getlist('reward')]
            for p in participants_reward:
                mturk_connection.approve_assignment(p.mturk_assignment_id)
                p.mturk_reward_paid = True
                p.save()

            participants_bonus = [participants.get(mturk_assignment_id=assignment_id)
                                  for assignment_id in request.POST.getlist('bonus')]
            for p in participants_bonus:
                bonus = boto.mturk.price.Price(amount=p.payoff_from_subsession.to_number)
                mturk_connection.grant_bonus(p.mturk_worker_id,
                                             p.mturk_assignment_id,
                                             bonus,
                                             reason="")
                p.mturk_bonus_paid = True
                p.save()

        return HttpResponseRedirect(reverse('session_payments', args=(session.pk,)))
