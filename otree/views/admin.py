# -*- coding: utf-8 -*-
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
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
from otree.views.demo import info_about_session_type
from otree import forms
from django.core.urlresolvers import reverse

class CreateSessionForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.session_type = kwargs.pop('session_type')
        super(CreateSessionForm, self).__init__(*args, **kwargs)

    num_participants = forms.IntegerField()

    def clean_num_participants(self):
        lcm = self.session_type.lcm()
        num_participants = self.cleaned_data['num_participants']
        if num_participants % lcm:
            raise forms.ValidationError('Number of participants must be a multiple of {}'.format(lcm))
        return num_participants

# FIXME: these decorators are not working together with issubclass?
#@user_passes_test(lambda u: u.is_staff)
#@login_required
class CreateSession(vanilla.FormView):

    form_class = CreateSessionForm
    template_name = 'otree/admin/CreateSession.html'

    @classmethod
    def url_pattern(cls):
        return r"^create_session/(?P<session_type>.+)/$"

    def dispatch(self, request, *args, **kwargs):
        session_type_name=urllib.unquote_plus(kwargs.pop('session_type'))
        self.session_type = SessionTypeDirectory().get_item(session_type_name)
        return super(CreateSession, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = info_about_session_type(self.session_type)
        kwargs.update(context)
        return super(CreateSession, self).get_context_data(**kwargs)

    def get_form(self, data=None, files=None, **kwargs):
        kwargs['session_type'] = self.session_type
        return super(CreateSession, self).get_form(data, files, **kwargs)

    def form_valid(self, form):

        session = create_session(
            type_name=self.session_type.name,
            num_participants = form.cleaned_data['num_participants'],
            preassign_players_to_groups=True,
        )
        admin_url = reverse('admin:%s_%s_change' % (session._meta.app_label, session._meta.module_name), args=(session.pk,))
        return HttpResponseRedirect(admin_url)

def escaped_create_session_url(session_type_name):
    return '/create_session/{}/'.format(urllib.quote_plus(session_type_name))

# FIXME: these decorators are not working together with issubclass?
#@user_passes_test(lambda u: u.is_staff)
#@login_required
class SessionTypes(vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^create_session/$"

    def get(self, *args, **kwargs):

        session_types_info = []
        for session_type in SessionTypeDirectory().select():
            session_types_info.append(
                {
                    'type_name': session_type.name,
                    'url': escaped_create_session_url(session_type.name),
                }
            )

        return TemplateResponse(self.request,
                                'otree/admin/SessionListing.html',
                                {'session_types_info': session_types_info})
