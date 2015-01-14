#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import time
import urllib
import uuid

from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse

import vanilla

import otree.common_internal
from otree.models.session import Session
from otree.session import (
    create_session, get_session_types_dict, get_session_types_list
)
from otree.views.demo import info_about_session_type
from otree import forms
from otree.views.abstract import GenericWaitPageMixin
from otree import adminlib

class CreateSessionForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.session_type = kwargs.pop('session_type')
        super(CreateSessionForm, self).__init__(*args, **kwargs)

    num_participants = forms.IntegerField()

    def clean_num_participants(self):
        lcm = self.session_type.lcm()
        num_participants = self.cleaned_data['num_participants']
        if num_participants % lcm:
            raise forms.ValidationError(
                'Number of participants must be a multiple of {}'.format(lcm)
            )
        return num_participants


class WaitUntilSessionCreated(GenericWaitPageMixin, vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^WaitUntilSessionCreated/(?P<session_pre_create_id>.+)/$"

    @classmethod
    def url(cls, pre_create_id):
        return "/WaitUntilSessionCreated/{}/".format(pre_create_id)

    def _is_ready(self):
        return Session.objects.filter(
            _pre_create_id=self._pre_create_id
        ).exists()

    def body_text(self):
        return 'Waiting until session created'

    def _response_when_ready(self):
        session = Session.objects.get(_pre_create_id=self._pre_create_id)
        urlname = 'admin:{}_{}_change'.format(
            session._meta.app_label, session._meta.module_name
        )
        admin_url = reverse(urlname, args=(session.pk,))
        return HttpResponseRedirect(admin_url)

    def dispatch(self, request, *args, **kwargs):
        self._pre_create_id = kwargs['session_pre_create_id']
        return super(WaitUntilSessionCreated, self).dispatch(
            request, *args, **kwargs
        )

    def _get_wait_page(self):
        return TemplateResponse(
            self.request, 'otree/WaitPage.html', {'view': self}
        )


def sleep_then_create_session(**kwargs):
    # hack: this sleep is to prevent locks on SQLite. This gives time to let
    # the page request finish before create_session is called,
    # because creating the session involves a lot of database I/O, which seems
    # to cause locks when multiple threads access at the same time.
    time.sleep(5)

    create_session(**kwargs)


# FIXME: these decorators are not working together with issubclass?
# @user_passes_test(lambda u: u.is_staff)
# @login_required
class CreateSession(vanilla.FormView):

    form_class = CreateSessionForm
    template_name = 'otree/admin/CreateSession.html'

    @classmethod
    def url_pattern(cls):
        return r"^create_session/(?P<session_type>.+)/$"

    def dispatch(self, request, *args, **kwargs):
        session_type_name = urllib.unquote_plus(kwargs.pop('session_type'))
        self.session_type = get_session_types_dict()[session_type_name]
        return super(CreateSession, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = info_about_session_type(self.session_type)
        kwargs.update(context)
        return super(CreateSession, self).get_context_data(**kwargs)

    def get_form(self, data=None, files=None, **kwargs):
        kwargs['session_type'] = self.session_type
        return super(CreateSession, self).get_form(data, files, **kwargs)

    def form_valid(self, form):
        pre_create_id = uuid.uuid4().hex
        kwargs = {
            'session_type_name': self.session_type.name,
            'num_participants': form.cleaned_data['num_participants'],
            '_pre_create_id': pre_create_id,
        }

        threading.Thread(
            target=sleep_then_create_session,
            kwargs=kwargs,
        ).start()

        return HttpResponseRedirect(WaitUntilSessionCreated.url(pre_create_id))


# FIXME: these decorators are not working together with issubclass?
# @user_passes_test(lambda u: u.is_staff)
# @login_required
class SessionTypes(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^create_session/$"

    def get(self, *args, **kwargs):
        session_types_info = []
        for session_type in get_session_types_list():
            session_types_info.append(
                {
                    'display_name': session_type.display_name,
                    'url': '/create_session/{}/'.format(session_type.name),
                }
            )

        return TemplateResponse(self.request,
                                'otree/admin/SessionListing.html',
                                {'session_types_info': session_types_info})

class SessionResults(vanilla.View):

    template_name = 'otree/admin/SessionResults.html'

    @classmethod
    def url_pattern(cls):
        return r"^session_results/(?P<session_pk>\d+)/$"

    def get(self, *args, **kwargs):

        session = Session.objects.get(pk=int(kwargs['session_pk']))
        participants = session.get_participants()


        subsession_colspans = []
        rows = []

        column_titles_dict = {}
        for app_name in session.session_type.app_sequence:
            models_module = otree.common_internal.get_models_module(app_name)

            player_fields = adminlib.get_all_fields(models_module.Player)
            group_fields = ['group.{}' for f in adminlib.get_all_fields(models_module.Group)]
            subsession_fields = ['subsession.{}' for f in adminlib.get_all_fields(models_module.Subsession)]

            column_titles_dict[app_name] = player_fields + group_fields + subsession_fields

        for participant in participants:
            row = []
            row.append(participant._id_in_session_display())
            for player in participant.get_players():
                field_names = column_titles_dict[player._meta.app_name]
                for field_name in field_names:
                    if callable(field_name):
                        pass #FIXME...finish this code






            # player fields, then group fields, then subsession fields







        session_types_info = []
        for session_type in get_session_types_list():
            session_types_info.append(
                {
                    'display_name': session_type.display_name,
                    'url': '/create_session/{}/'.format(session_type.name),
                }
            )

        return TemplateResponse(self.request,
                                'otree/admin/SessionListing.html',
                                {'session_types_info': session_types_info})
