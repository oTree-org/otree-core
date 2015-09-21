#!/usr/bin/env python
# encoding: utf-8

import urlparse
import datetime

from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseServerError
from django.shortcuts import get_object_or_404

import vanilla

import boto.mturk.connection
from boto.mturk.connection import MTurkRequestError
from boto.mturk.qualification import Qualifications

import IPy

import otree
from otree import forms
from otree.views.abstract import AdminSessionPageMixin
from otree.checks.mturk import validate_session_for_mturk
from otree import deprecate


class MTurkError(Exception):

    def __init__(self, request, message):
        self.message = message
        messages.error(request, message, extra_tags='safe')

    def __str__(self):
        return self.message


class MTurkConnection(boto.mturk.connection.MTurkConnection):

    def __init__(self, request, in_sandbox=True):
        if in_sandbox:
            self.mturk_host = settings.MTURK_SANDBOX_HOST
        else:
            self.mturk_host = settings.MTURK_HOST
        self.request = request

    def __enter__(self):
        self = boto.mturk.connection.MTurkConnection(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            host=self.mturk_host,
        )
        return self

    def __exit__(self, exc_type, value, traceback):
        # TODO: need to take care of possible errors (login,
        # "service not approved")
        if exc_type is MTurkRequestError:
            MTurkError(self.request, value.message)
        return False


class SessionCreateHitForm(forms.Form):

    in_sandbox = forms.BooleanField(
        required=False,
        help_text="Do you want HIT published on MTurk sandbox?")
    title = forms.CharField()
    description = forms.CharField()
    keywords = forms.CharField()
    money_reward = forms.RealWorldCurrencyField()
    assignments = forms.IntegerField(
        label="Number of assignments",
        help_text="How many unique Workers do you want to work on the HIT?")
    minutes_allotted_per_assignment = forms.IntegerField(
        label="Minutes allotted per assignment",
        required=False,
        help_text=(
            "Number of minutes, that a Worker has to "
            "complete the HIT after accepting it."
            "Leave it blank if you don't want to specify it."))
    expiration_hours = forms.IntegerField(
        label="Hours until HIT expiration",
        required=False,
        help_text=(
            "Number of hours after which the HIT "
            "is no longer available for users to accept. "
            "Leave it blank if you don't want to specify it."))

    def __init__(self, *args, **kwargs):
        super(SessionCreateHitForm, self).__init__(*args, **kwargs)
        self.fields['assignments'].widget.attrs['readonly'] = True


class SessionCreateHit(AdminSessionPageMixin, vanilla.FormView):
    '''This view creates mturk HIT for session provided in request
    AWS externalQuestion API is used to generate HIT.

    '''
    form_class = SessionCreateHitForm

    @classmethod
    def url_name(cls):
        return 'session_create_hit'

    def in_public_domain(self, request, *args, **kwargs):
        """This method validates if oTree are published on a public domain
        because mturk need it

        """
        host = request.get_host().lower()
        if ":" in host:
            host = host.split(":", 1)[0]
        if host == "localhost":
            return False
        try:
            ip = IPy.IP(host)
            return ip.iptype() == "PUBLIC"
        except ValueError:
            # probably is a public domain
            return True

    def get(self, request, *args, **kwargs):
        validate_session_for_mturk(request, self.session)
        mturk_settings = self.session.config['mturk_hit_settings']
        initial = {
            'title': mturk_settings['title'],
            'description': mturk_settings['description'],
            'keywords': ', '.join(mturk_settings['keywords']),
            'money_reward': self.session.config['participation_fee'],
            'in_sandbox': settings.DEBUG,
            'minutes_allotted_per_assignment': (
                mturk_settings['minutes_allotted_per_assignment']
            ),
            'expiration_hours': mturk_settings['expiration_hours'],
            'assignments': self.session.mturk_num_participants,
        }
        form = self.get_form(initial=initial)
        context = self.get_context_data(form=form)
        context['mturk_enabled'] = (
            bool(settings.AWS_ACCESS_KEY_ID) and
            bool(settings.AWS_SECRET_ACCESS_KEY)
        )
        url = self.request.build_absolute_uri(
            reverse('session_create_hit', args=(self.session.pk,))
        )
        secured_url = urlparse.urlunparse(
            urlparse.urlparse(url)._replace(scheme='https')
        )
        context['secured_url'] = secured_url

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        form = self.get_form(
            data=request.POST,
            files=request.FILES
        )
        if not form.is_valid():
            return self.form_invalid(form)
        session = self.session
        in_sandbox = 'in_sandbox' in form.data
        # session can't be created
        if (not self.in_public_domain(request, *args, **kwargs) and
           not in_sandbox):
                msg = (
                    '<h1>Error: '
                    'oTree must run on a public domain for Mechanical Turk'
                    '</h1>')
                return HttpResponseServerError(msg)
        with MTurkConnection(self.request, in_sandbox) as mturk_connection:
            mturk_settings = session.config['mturk_hit_settings']
            qualification_id = mturk_settings.get(
                'grant_qualification_id', None)
            # verify that specified qualification type
            # for preventing retakes exists on mturk server
            if qualification_id:
                try:
                    mturk_connection.get_qualification_type(qualification_id)
                except MTurkRequestError as e:
                    code = 'AWS.MechanicalTurk.QualificationTypeDoesNotExist'
                    if e.error_code == code:
                        msg = (
                            "In settings.py you specified qualification id "
                            " '%s' which doesn't exist on mturk server. "
                            "Please verify its validity.")
                        msg = msg.format('grant_qualification_id')
                        messages.error(request, msg)
                        return HttpResponseRedirect(
                            reverse('session_create_hit', args=(session.pk,)))
                else:
                    session.mturk_qualification_type_id = qualification_id

            url_landing_page = self.request.build_absolute_uri(
                reverse('mturk_landing_page', args=(session.code,)))

            # updating schema from http to https
            # this is compulsory for MTurk exteranlQuestion
            secured_url_landing_page = urlparse.urlunparse(
                urlparse.urlparse(url_landing_page)._replace(scheme='https'))

            # TODO: validate, that the server support https
            #       (heroku does support by default)
            # TODO: validate that there is enought money for the hit
            reward = boto.mturk.price.Price(
                amount=float(form.data['money_reward']))

            # creating external questions, that would be passed to the hit
            external_question = boto.mturk.question.ExternalQuestion(
                secured_url_landing_page, mturk_settings['frame_height'])

            qualifications = mturk_settings.get('qualification_requirements')

            # deprecated summer 2015: remove this
            if (not qualifications
               and hasattr(settings, 'MTURK_WORKER_REQUIREMENTS')):
                    deprecate.dwarning(
                        'The MTURK_WORKER_REQUIREMENTS setting has been '
                        'deprecated. You should instead use '
                        '"qualification_requirements" as shown here: '
                        'https://github.com/oTree-org/oTree/blob/master/'
                        'settings.py')
                    qualifications = settings.MTURK_WORKER_REQUIREMENTS

            mturk_hit_parameters = {
                'title': form.cleaned_data['title'],
                'description': form.cleaned_data['description'],
                'keywords': [
                    k.strip() for k in form.cleaned_data['keywords'].split(',')
                ],
                'question': external_question,
                'max_assignments': form.cleaned_data['assignments'],
                'reward': reward,
                'response_groups': ('Minimal', 'HITDetail'),
                'qualifications': Qualifications(qualifications),
            }
            if form.cleaned_data['minutes_allotted_per_assignment']:
                mturk_hit_parameters['duration'] = datetime.timedelta(
                    minutes=(
                        form.cleaned_data['minutes_allotted_per_assignment']))

            if form.cleaned_data['expiration_hours']:
                mturk_hit_parameters['lifetime'] = datetime.timedelta(
                    hours=form.cleaned_data['expiration_hours'])

            hit = mturk_connection.create_hit(**mturk_hit_parameters)
            session.mturk_HITId = hit[0].HITId
            session.mturk_HITGroupId = hit[0].HITGroupId
            session.mturk_sandbox = in_sandbox
            session.save()

        return HttpResponseRedirect(
            reverse('session_create_hit', args=(session.pk,)))


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
            otree.models.session.Session, pk=kwargs['session_pk'])
        with MTurkConnection(self.request,
                             session.mturk_sandbox) as mturk_connection:
            workers_with_submit = [
                completed_assignment.WorkerId
                for completed_assignment in
                mturk_connection.get_assignments(session.mturk_HITId)]
            participants = session.participant_set.filter(
                mturk_worker_id__in=workers_with_submit)
            participants_reward = [
                participants.get(mturk_assignment_id=assignment_id)
                for assignment_id in request.POST.getlist('reward')]
            for p in participants_reward:
                mturk_connection.approve_assignment(p.mturk_assignment_id)
                p.mturk_reward_paid = True
                p.save()

            participants_bonus = [
                participants.get(mturk_assignment_id=assignment_id)
                for assignment_id in request.POST.getlist('bonus')]
            for p in participants_bonus:
                bonus = boto.mturk.price.Price(
                    amount=p.payoff_in_real_world_currency().to_number())
                mturk_connection.grant_bonus(
                    p.mturk_worker_id, p.mturk_assignment_id,
                    bonus, reason="Thank you.")
                p.mturk_bonus_paid = True
                p.save()
        messages.success(request, "Your payment was successful")
        return HttpResponseRedirect(
            reverse('session_payments', args=(session.pk,)))
