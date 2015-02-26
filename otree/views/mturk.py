#!/usr/bin/env python
# encoding: utf-8

import urlparse
import vanilla
import boto.mturk.connection

from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404

import otree


class CreateHitFromSession(vanilla.View):
    '''
        This view creates mturk HIT from given session
        using externalQuestion data structure.
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
        response = super(CreateHitFromSession, self).dispatch(
            request, *args, **kwargs
        )
        return response

    def get(self, request, *args, **kwargs):
        session = self.session
        if session.mturk_HITId:
            return HttpResponseRedirect(reverse('admin_home'))
        # if we are in DEBUG mode all HITS are created in mturk sandbox
        if settings.DEBUG:
            mturk_host = settings.MTURK_SANDBOX_HOST
        else:
            mturk_host = settings.MTURK_HOST

        mturk_connection = boto.mturk.connection.MTurkConnection(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            host=mturk_host,
        )
        url_landing_page = self.request.build_absolute_uri(reverse('mturk_landing_page', args=(session.code,)))
        # updating schema from http to https
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
            You have created a hit for session <b>%s</b>.<br>
            To look at the hit as a <em>requester</em>
            follow this <a href="%s" target="_blank">link</a>.<br>
            To look at the hit as a <em>worker</em>
            follow this <a href="%s" target="_blank">link</a>.
            """ % (session.code,
                   session.mturk_requester_url(),
                   session.mturk_worker_url())

        messages.success(request, message, extra_tags='safe')
        return HttpResponseRedirect(reverse('admin_home'))
