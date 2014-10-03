# -*- coding: utf-8 -*-
from django.shortcuts import get_object_or_404, render_to_response
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
import vanilla
import otree.constants as constants
from otree.sessionlib.models import Session
from otree.session import create_session, SessionTypeDirectory
import threading
import time
import urllib
from otree.common import get_session_module, get_models_module, app_name_format
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from otree.views.demo import escaped_start_link_url, info_about_session_type
from django import forms

@user_passes_test(lambda u: u.is_staff)
@login_required
class SessionTypes(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r'^session_types/$'

    def get(self, *args, **kwargs):

        session_types_info = []
        for session_type in SessionTypeDirectory.select():
            session_types_info.append(
                {
                    'type_name': session_type.name,
                    'url': escaped_start_link_url(session_type.name),
                    'doc': session_type.doc or '',
                    'subsession_apps': ', '.join([app_name_format(app_name) for app_name in session_type.subsession_apps]),
                }
            )
        return render_to_response('otree/admin/session_types.html', {'session_types_info': session_types_info})

class CreateSessionForm(forms.Form):

    def

    def clean_num_participants(self, cleaned_data):
        if not cleaned_data['num_participants'] %


@user_passes_test(lambda u: u.is_staff)
@login_required
class CreateSession(vanilla.FormView):

    def get_success_url(self):


    @classmethod
    def url_pattern(cls):
        return r"^admin/session_type/(?P<session_type>.+)/create$"

    def dispatch(self, request, *args, **kwargs):
        session_type_name=urllib.unquote_plus(kwargs['session_type'])
        self.session_type = SessionTypeDirectory().get_item(session_type_name)

    def get(self, *args, **kwargs):

        context = info_about_session_type(session_type)
        return render_to_response('otree/admin/CreateSession.html', context)

    def post(self, request, *args, **kwargs):


    def form_valid(self, form):
        num_participants = self.request.POST['num_participants']
        session = create_session(

            num_participants
        )
        return HttpResponseRedirect(self.get_success_url())