#!/usr/bin/env python
# encoding: utf-8

import urlparse
import datetime

from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404

import vanilla

import boto.mturk.connection
from boto.mturk.connection import MTurkRequestError
from boto.mturk.qualification import Qualifications

import otree
from otree import forms
from otree.views.abstract import AdminSessionPageMixin


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
    in_sandbox = forms.BooleanField(required=False,
                                    help_text="""
                                    Do you want HIT published
                                    on MTurk sandbox?
                                    """)
    title = forms.CharField()
    description = forms.CharField()
    keywords = forms.CharField()
    money_reward = forms.RealWorldCurrencyField()
    assignments = forms.IntegerField(
        label="Number of assignments",
        help_text=("How many unique Workers do you want to work on the HIT? "
                   "You may want this number to be lower than participants "
                   "in the oTree session to account for people who accepts "
                   "and then return the HIT.")
    )
    duration = forms.IntegerField(
        label="Assignment duration in minutes",
        required=False,
        help_text=("The amount of time, in minutes, that a Worker has to "
                   "complete the HIT after accepting it."
                   "Leave it blank if you don't want to specify it.")
    )
    lifetime = forms.IntegerField(
        label="Lifetime in hours",
        required=False,
        help_text=("An amount of time, in hours, after which the HIT "
                   "is no longer available for users to accept. "
                   "Leave it blank if you don't want to specify it.")
    )

    qualifications_choices = []
    for i, q in enumerate(settings.MTURK_WORKER_REQUIREMENTS):
        label = ', '.join(
            (q.__class__.__name__,
             q.comparator,
             str(q.integer_value) if q.integer_value else q.locale)
        )
        qualifications_choices.append((i, label))
    worker_qualifications = forms.MultipleChoiceField(
        choices=qualifications_choices,
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        help_text=("You can extend the list of possible "
                   "requirements in settings.py")
    )

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop('session', None)
        super(SessionCreateHitForm, self).__init__(*args, **kwargs)

    def clean_assignments(self):
        data = self.cleaned_data['assignments']
        if data > len(self.session.get_participants()):
            raise forms.ValidationError("""Number of Mturk assignments should be less or equal
                                           than number of participants in
                                           oTree session.""")
        return data


class SessionCreateHit(AdminSessionPageMixin, vanilla.FormView):
    '''
        This view creates mturk HIT for session provided in request
        AWS externalQuestion API is used to generate HIT.
    '''
    form_class = SessionCreateHitForm

    @classmethod
    def url_name(cls):
        return 'session_create_hit'

    def get(self, request, *args, **kwargs):
        mturk_hit_settings = self.session.session_type['mturk_hit_settings']
        initial = {
            'title': mturk_hit_settings['title'],
            'description': mturk_hit_settings['description'],
            'keywords': ', '.join(mturk_hit_settings['keywords']),
            'money_reward': self.session.fixed_pay,
            'assignments': len(self.session.get_participants()),
            'in_sandbox': settings.DEBUG
        }
        form = self.get_form(initial=initial)
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        form = self.get_form(
            data=request.POST,
            session=self.session,
            files=request.FILES
        )
        if not form.is_valid():
            return self.form_invalid(form)
        session = self.session
        in_sandbox = 'in_sandbox' in form.data
        with MTurkConnection(self.request, in_sandbox) as mturk_connection:
            url_landing_page = self.request.build_absolute_uri(
                reverse('mturk_landing_page', args=(session.code,))
            )

            # updating schema from http to https
            # this is compulsory for MTurk exteranlQuestion
            secured_url_landing_page = urlparse.urlunparse(
                urlparse.urlparse(url_landing_page)._replace(scheme='https')
            )

            # TODO: validate, that the server support https
            #       (heroku does support by default)
            # TODO: validate that there is enought money for the hit
            reward = boto.mturk.price.Price(
                amount=float(form.data['money_reward'])
            )

            # creating external questions, that would be passed to the hit
            external_question = boto.mturk.question.ExternalQuestion(
                secured_url_landing_page,
                session.session_type['mturk_hit_settings']['frame_height'],
            )
            qualifications = Qualifications()
            for q_id in form.data.get('worker_qualifications', []):
                qualifications.add(
                    settings.MTURK_WORKER_REQUIREMENTS[int(q_id)]
                )
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
                'qualifications': qualifications,
            }
            if form.cleaned_data['duration']:
                mturk_hit_parameters['duration'] = datetime.timedelta(
                    minutes=form.cleaned_data['duration']
                )

            if form.cleaned_data['lifetime']:
                mturk_hit_parameters['lifetime'] = datetime.timedelta(
                    hours=form.cleaned_data['lifetime']
                )

            hit = mturk_connection.create_hit(**mturk_hit_parameters)
            session.mturk_HITId = hit[0].HITId
            session.mturk_HITGroupId = hit[0].HITGroupId
            session.mturk_sandbox = in_sandbox
            session.save()

        return HttpResponseRedirect(reverse('session_create_hit',
                                            args=(session.pk,)))


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
        participants = session.participant_set.exclude(
            mturk_assignment_id__isnull=True
        ).exclude(mturk_assignment_id="")
        with MTurkConnection(self.request,
                             session.mturk_sandbox) as mturk_connection:
            participants_reward = [
                participants.get(mturk_assignment_id=assignment_id)
                for assignment_id in request.POST.getlist('reward')
            ]
            for p in participants_reward:
                mturk_connection.approve_assignment(p.mturk_assignment_id)
                p.mturk_reward_paid = True
                p.save()

            participants_bonus = [
                participants.get(mturk_assignment_id=assignment_id)
                for assignment_id in request.POST.getlist('bonus')
            ]
            for p in participants_bonus:
                bonus = boto.mturk.price.Price(
                    amount=p.payoff_from_subsessions().to_number()
                )
                mturk_connection.grant_bonus(
                    p.mturk_worker_id, p.mturk_assignment_id,
                    bonus, reason="Good job!!!"
                )
                p.mturk_bonus_paid = True
                p.save()
        messages.success(request, "Your payment was successful")
        return HttpResponseRedirect(
            reverse('session_payments', args=(session.pk,))
        )
