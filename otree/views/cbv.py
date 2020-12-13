import json
import asyncio
import os
import random
from asgiref.sync import async_to_sync
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse

from otree import settings
from otree.common import CSRF_TOKEN_NAME, AUTH_COOKIE_NAME, AUTH_COOKIE_VALUE
from otree.database import db
from otree.models import Session
from otree.templating import render

ALWAYS_UNRESTRICTED = 'ALWAYS_UNRESTRICTED'
UNRESTRICTED_IN_DEMO_MODE = 'UNRESTRICTED_IN_DEMO_MODE'

_admin_message_queue = []


def enqueue_admin_message(bootstrap_alert_type, msg):
    _admin_message_queue.append(dict(alert_type=bootstrap_alert_type, msg=msg))


class AdminView(HTTPEndpoint):
    csrf_exempt = False
    request: Request
    _requires_login = False
    form_class = None
    _form_data = None

    def _is_unauthorized(self):
        return (
            self._requires_login
            and not self.request.session.get(AUTH_COOKIE_NAME) == AUTH_COOKIE_VALUE
        )

    async def dispatch(self) -> None:
        self.request = request = Request(self.scope, receive=self.receive)
        response = await run_in_threadpool(self.inner_dispatch, request)
        await response(self.scope, self.receive, self.send)

    def get_post_data(self) -> FormData:
        if not self._form_data:
            self._form_data = async_to_sync(self.request.form)()
        return self._form_data

    def inner_dispatch(self, request: Request):
        if self._is_unauthorized():
            return self.redirect('Login')
        resp = self.intercept_dispatch(**request.path_params)
        if resp:
            return resp
        if request.method.lower() == 'post':
            if not (self.csrf_exempt or os.getenv('OTREE_SKIP_CSRF')):
                post_data = self.get_post_data()
                form_token = post_data.get(CSRF_TOKEN_NAME)
                cookie = request.session.get(CSRF_TOKEN_NAME)
                if not form_token or not cookie or (form_token != cookie):
                    return Response(status_code=403, content='CSRF verification failed')

            return self.post(request, **request.path_params)
        return self.get(request, **request.path_params)

    def intercept_dispatch(self, **kwargs):
        pass

    def get(self, request, **kwargs):
        context = {}
        form = self.get_form()
        if form:
            context['form'] = form
        context = self.get_context_data(**context)
        return self.render_to_response(context)

    def get_form(self):
        if self.form_class:
            return self.form_class()

    def post(self, request, *args, **kwargs):
        form = self.form_class(formdata=self.get_post_data())
        if form.validate():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        return self.redirect(self.get_success_url())

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        csrf_value = self.request.session.get(CSRF_TOKEN_NAME)
        if not csrf_value:
            csrf_value = str(random.randint(10 ** 9, 10 ** 10))
            self.request.session[CSRF_TOKEN_NAME] = csrf_value
        token_input = (
            f'<input type="hidden" name="{CSRF_TOKEN_NAME}" value="{csrf_value}">'
        )
        kwargs[CSRF_TOKEN_NAME] = token_input
        # import functools
        kwargs.update(
            view=self,
            admin_message_queue=_admin_message_queue,
            is_debug=settings.DEBUG,
            http_request=self.request,
            current_page_name=self.__class__.__name__,
            url_for=self.request.url_for,
        )
        # vars_for_template has highest priority
        kwargs.update(self.vars_for_template())
        return kwargs

    def vars_for_template(self):
        '''
        simpler to use vars_for_template, but need to use get_context_data when:
        -   you need access to the context produced by the parent class,
            such as the form
        '''
        return {}

    def render_to_response(self, context):
        return render(self.get_template_name(), context)

    def get_success_url(self):
        return self.request.url

    def get_template_name(self):
        return 'otree/{}.html'.format(self.__class__.__name__)

    def redirect(self, url_name, **kwargs) -> RedirectResponse:
        return RedirectResponse(
            self.request.url_for(url_name, **kwargs), status_code=302
        )


class AdminSessionPage(AdminView):
    session: Session

    @classmethod
    def url_pattern(cls):
        return r"/%s/{code}" % cls.__name__

    def get_context_data(self, **kwargs):
        return super().get_context_data(session=self.session, **kwargs)

    def inner_dispatch(self, request):
        self.session = db.get_or_404(Session, code=request.path_params['code'])
        return super().inner_dispatch(request)


REST_KEY_NAME = 'OTREE_REST_KEY'
REST_KEY_HEADER = 'otree-rest-key'


def _HttpResponseForbidden(msg):
    return Response(msg, status_code=403)


class BaseRESTView(HTTPEndpoint):
    """
    async so that i can get request.json().
    inner_post should also call group_send, at there are complications with doing sync_group_send.
    
    """

    def post(self, request: Request):
        if settings.AUTH_LEVEL in ['DEMO', 'STUDY']:
            REST_KEY = os.getenv(REST_KEY_NAME)  # put it here for easy testing
            if not REST_KEY:
                return _HttpResponseForbidden(
                    f'Env var {REST_KEY_NAME} must be defined to use REST API'
                )
            submitted_rest_key = request.headers.get(REST_KEY_HEADER)
            if not submitted_rest_key:
                return _HttpResponseForbidden(
                    f'HTTP Request Header {REST_KEY_HEADER} is missing'
                )
            if REST_KEY != submitted_rest_key:
                return _HttpResponseForbidden(
                    f'HTTP Request Header {REST_KEY_HEADER} is incorrect'
                )
        payload = asyncio.run(request.json())
        return self.inner_post(**payload)

    def inner_post(self, **kwargs):
        raise NotImplementedError
