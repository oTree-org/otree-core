from django.http import HttpResponseServerError
import time
from otree.common import missing_db_tables
import logging
import re
from .oTree import settings
from django.urls import reverse
from django.shortcuts import redirect
from django.contrib.auth import logout


logger = logging.getLogger('otree.perf')


def perf_middleware(get_response):
    # One-time configuration and initialization.

    def middleware(request):
        start = time.time()

        response = get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        # heroku has 'X-Request-ID', which Django translates to
        # the following:
        request_id = request.META.get('HTTP_X_REQUEST_ID')
        if request_id:
            # only log this info on Heroku
            elapsed = time.time() - start
            msec = int(elapsed * 1000)
            msg = f'own_time={msec}ms request_id={request_id}'
            logger.info(msg)

        return response

    return middleware


class CheckDBMiddleware:
    synced = None

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not CheckDBMiddleware.synced:
            # very fast, 0.01-0.02 seconds for the whole check
            missing_tables = missing_db_tables()
            if missing_tables:
                listed_tables = missing_tables[:3]
                unlisted_tables = missing_tables[3:]
                msg = (
                    "Your database is not ready. Try resetting the database "
                    "(Missing tables for {}, and {} other models). "
                ).format(', '.join(listed_tables), len(unlisted_tables))
                return HttpResponseServerError(msg)
            else:
                CheckDBMiddleware.synced = True
        return self.get_response(request)


EXEMPT_URLS = [re.compile(settings.LOGIN_URL.lstrip('/'))]
if hasattr(settings, 'LOGIN_EXEMPT_URLS'):
    EXEMPT_URLS += [re.compile(url) for url in settings.LOGIN_EXEMPT_URLS]


class LoginRequiredMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    # def process_view(self, request, view_func, view_args, view_kwargs):
    #     assert hasattr(request, 'user')
    #     path = request.path_info.lstrip('/')
    #     url_is_exempt = any(url.match(path) for url in EXEMPT_URLS)
    #
    #     if path == reverse('logout').lstrip('/'):
    #         logout(request)
    #
    #     if request.user.is_authenticated and url_is_exempt and path == 'admin/':
    #         return redirect(settings.LOGIN_REDIRECT_URL)
    #     elif request.user.is_authenticated or url_is_exempt:
    #         return None
    #     else:
    #         return redirect(settings.LOGIN_URL)
