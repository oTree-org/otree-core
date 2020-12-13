import importlib
import json
import logging
import os
import time
from typing import Optional

import otree.common2
import vanilla
from django.conf import settings
from django.core import signals
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.core.handlers.exception import handle_uncaught_exception
from django.http import (
    HttpResponseRedirect,
    Http404,
    HttpResponseForbidden,
    HttpResponseNotFound,
)
from django.http.multipartparser import MultiPartParserError
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import get_resolver, get_urlconf
from django.urls import resolve
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.decorators.cache import never_cache, cache_control
import django.forms.models
from django.views.decorators.csrf import csrf_exempt
import otree.channels.utils as channel_utils
import otree.common
import otree.constants
from otree.db import idmap
import otree.forms
import otree.models
import otree.tasks
from otree.bots.bot import bot_prettify_post_data, ExpectError
from otree.common import (
    get_app_label_from_import_path,
    get_dotted_name,
    get_admin_secret_code,
    DebugTable,
    BotError,
    ResponseForException,
)
from otree.lookup import get_min_idx_for_app, get_page_lookup
from otree.models import Participant, Session, BaseGroup, BaseSubsession
from otree.models_concrete import (
    CompletedSubsessionWaitPage,
    CompletedGroupWaitPage,
    CompletedGBATWaitPage,
    UndefinedFormModel,
)
from otree import export

# this is an expensive import
import otree.bots.browser as browser_bots

logger = logging.getLogger(__name__)

UNHANDLED_EXCEPTIONS = (
    Http404,
    PermissionDenied,
    MultiPartParserError,
    SuspiciousOperation,
    SystemExit,
)


def response_for_exception(request, exc):
    '''simplified from Django 1.11 source.
    The difference is that we use the exception that was passed in,
    rather than referencing sys.exc_info(), which gives us the ResponseForException
    the original exception was wrapped in, which we don't want to show to users.
        '''
    from django.utils.log import log_response  # expensive import

    if isinstance(exc, UNHANDLED_EXCEPTIONS):
        '''copied from Django source, but i don't think these
        exceptions will actually occur.'''
        raise exc
    signals.got_request_exception.send(sender=None, request=request)
    exc_info = (type(exc), exc, exc.__traceback__)
    response = handle_uncaught_exception(request, get_resolver(get_urlconf()), exc_info)
    log_response(
        '%s: %s',
        response.reason_phrase,
        request.path,
        response=response,
        request=request,
        exc_info=exc,
    )
    if settings.DEBUG:
        response.content = response.content.split(b'<div id="requestinfo">')[0]

    # Force a TemplateResponse to be rendered.
    if not getattr(response, 'is_rendered', True) and callable(
        getattr(response, 'render', None)
    ):
        response = response.render()

    return response


ADMIN_SECRET_CODE = get_admin_secret_code()


def get_view_from_url(url):
    view_func = resolve(url).func
    module = importlib.import_module(view_func.__module__)
    Page = getattr(module, view_func.__name__)
    return Page


BOT_COMPLETE_HTML_MESSAGE = '''
<html>
    <head>
        <title>Bot completed</title>
    </head>
    <body>Bot completed</body>
</html>
'''


class FormPageOrInGameWaitPage(vanilla.View):
    """
    View that manages its position in the group sequence.
    for both players and experimenters
    """

    template_name = None

    is_debug = settings.DEBUG

    def inner_dispatch(self):
        '''inner dispatch function'''
        raise NotImplementedError()

    def get_template_names(self):
        raise NotImplementedError()

    @classmethod
    def url_pattern(cls, name_in_url):
        p = r'^p/(?P<participant_code>\w+)/{}/{}/(?P<page_index>\d+)/$'.format(
            name_in_url, cls.__name__
        )
        return p

    @classmethod
    def get_url(cls, participant_code, name_in_url, page_index):
        '''need this because reverse() is too slow in create_session'''
        return r'/p/{pcode}/{name_in_url}/{ClassName}/{page_index}/'.format(
            pcode=participant_code,
            name_in_url=name_in_url,
            ClassName=cls.__name__,
            page_index=page_index,
        )

    @classmethod
    def url_name(cls):
        '''using dots seems not to work'''
        return get_dotted_name(cls).replace('.', '-')

    def _redirect_to_page_the_user_should_be_on(self):
        return HttpResponseRedirect(self.participant._url_i_should_be_on())

    @method_decorator(csrf_exempt)
    @method_decorator(never_cache)
    @method_decorator(
        cache_control(must_revalidate=True, max_age=0, no_cache=True, no_store=True)
    )
    def dispatch(self, request, participant_code, **kwargs):
        with idmap.use_cache():
            try:
                participant = Participant.objects.get(code=participant_code)
            except Participant.DoesNotExist:
                msg = (
                    "This user ({}) does not exist in the database. "
                    "Maybe the database was reset."
                ).format(participant_code)
                return HttpResponseNotFound(msg)

            # if the player tried to skip past a part of the subsession
            # (e.g. by typing in a future URL)
            # or if they hit the back button to a previous subsession
            # in the sequence.
            url_should_be_on = participant._url_i_should_be_on()
            if not self.request.path == url_should_be_on:
                return HttpResponseRedirect(url_should_be_on)

            self.set_attributes(participant)

            try:
                response = self.inner_dispatch()
                # need to render the response before saving objects,
                # because the template might call a method that modifies
                # player/group/etc.
                if hasattr(response, 'render'):
                    response.render()
            except (ResponseForException, ExpectError) as exc:
                response = response_for_exception(
                    self.request, exc.__cause__ or exc.__context__
                )
            except Exception as exc:
                # this is still necessary, e.g. if an attribute on the page
                # is invalid, like form_fields, form_model, etc.
                response = response_for_exception(self.request, exc)

        return response

    def get_context_data(self, **context):

        context.update(
            view=self,
            object=getattr(self, 'object', None),
            player=self.player,
            group=self.group,
            subsession=self.subsession,
            session=self.session,
            participant=self.participant,
            Constants=self._Constants,
            timer_text=getattr(self, 'timer_text', None),
        )

        views_module = otree.common.get_pages_module(
            self.subsession._meta.app_config.name
        )
        if hasattr(views_module, 'vars_for_all_templates'):
            vars_for_template = views_module.vars_for_all_templates(self)
        else:
            vars_for_template = {}

        try:
            user_vars = self.vars_for_template()
            context['js_vars'] = self.js_vars()
        except:
            raise ResponseForException

        vars_for_template.update(user_vars or {})

        context.update(vars_for_template)

        if settings.DEBUG:
            self.debug_tables = self._get_debug_tables(vars_for_template)
        return context

    def render_to_response(self, context):
        """
        Given a context dictionary, returns an HTTP response.
        """
        return TemplateResponse(
            request=self.request, template=self.get_template_names(), context=context
        )

    def vars_for_template(self):
        return {}

    def js_vars(self):
        return {}

    def _get_debug_tables(self, vars_for_template):

        tables = []
        if vars_for_template:
            # use repr() so that we can distinguish strings from numbers
            # and can see currency types, etc.
            items = [(k, repr(v)) for (k, v) in vars_for_template.items()]
            rows = sorted(items)
            tables.append(DebugTable(title='vars_for_template', rows=rows))

        player = self.player
        participant = self.participant
        basic_info_table = DebugTable(
            title='Basic info',
            rows=[
                ('ID in group', player.id_in_group),
                ('Group', player.group_id),
                ('Round number', player.round_number),
                ('Participant', participant._numeric_label()),
                ('Participant label', participant.label or ''),
                ('Session code', participant._session_code),
            ],
        )

        tables.append(basic_info_table)

        return tables

    def _is_displayed(self):
        try:
            return self.is_displayed()
        except:
            raise ResponseForException

    @property
    def group(self) -> BaseGroup:
        '''can't cache self._group_pk because group can change'''
        return self.player.group

    @property
    def subsession(self) -> BaseSubsession:
        '''so that it doesn't rely on player'''
        # this goes through idmap cache, so no perf hit
        return self.SubsessionClass.objects.get(pk=self._subsession_pk)

    @property
    def session(self) -> Session:
        return Session.objects.get(pk=self._session_pk)

    def set_attributes(self, participant):

        lookup = get_page_lookup(participant._session_code, participant._index_in_pages)
        self._lookup = lookup

        app_name = lookup.app_name

        models_module = otree.common.get_models_module(app_name)
        self._Constants = models_module.Constants
        self.PlayerClass = getattr(models_module, 'Player')
        self.GroupClass = getattr(models_module, 'Group')
        self.SubsessionClass = getattr(models_module, 'Subsession')
        self.player = self.PlayerClass.objects.get(
            participant=participant, round_number=lookup.round_number
        )
        self._subsession_pk = lookup.subsession_id
        self.round_number = lookup.round_number
        self._session_pk = lookup.session_pk
        # simpler if we set it directly so that we can do tests without idmap cache
        self._participant_pk = participant.pk
        # setting it directly makes testing easier (tests dont need to use cache)
        self.participant: Participant = participant

        # it's already validated that participant is on right page
        self._index_in_pages = participant._index_in_pages

        # for the participant changelist
        participant._current_app_name = app_name
        participant._current_page_name = self.__class__.__name__
        participant._last_request_timestamp = time.time()
        participant._round_number = lookup.round_number

        self._is_frozen = True

    def set_attributes_waitpage_clone(self, *, original_view: 'WaitPage'):
        '''put it here so it can be compared with set_attributes...
        but this is really just a method on wait pages'''
        # make a clean copy for AAPA
        # self.player and self.participant etc are undefined
        # and no objects are cached inside it
        # and it doesn't affect the current instance

        self._Constants = original_view._Constants
        self.GroupClass = original_view.GroupClass
        self.SubsessionClass = original_view.SubsessionClass
        self._subsession_pk = original_view._subsession_pk
        self._session_pk = original_view._session_pk
        self.round_number = original_view.round_number

    def _increment_index_in_pages(self):
        # when is this not the case?
        assert self._index_in_pages == self.participant._index_in_pages

        # we should allow a user to move beyond the last page if it's mturk
        # also in general maybe we should show the 'out of sequence' page

        # we skip any page that is a sequence page where is_displayed
        # evaluates to False to eliminate unnecessary redirection

        page_index_to_skip_to = self._get_next_page_index_if_skipping_apps()
        is_skipping_apps = bool(page_index_to_skip_to)

        for page_index in range(
            # go to max_page_index+2 because range() skips the last index
            # and it's possible to go to max_page_index + 1 (OutOfRange)
            self._index_in_pages + 1,
            self.participant._max_page_index + 2,
        ):
            self.participant._index_in_pages = page_index
            if page_index == self.participant._max_page_index + 1:
                # break and go to OutOfRangeNotification
                break
            if is_skipping_apps and page_index == page_index_to_skip_to:
                break

            url = self.participant._url_i_should_be_on()

            Page = get_view_from_url(url)
            page: FormPageOrInGameWaitPage = Page()

            page.set_attributes(self.participant)
            if not is_skipping_apps:
                if page._lookup.is_first_in_round:
                    # we have moved to a new round.
                    page.player.start()
                if page._is_displayed():
                    break

            # if it's a wait page, record that they visited
            # but don't run after_all_players_arrive
            if isinstance(page, WaitPage):

                if page.group_by_arrival_time:
                    # keep looping
                    # if 1 participant can skip the page,
                    # then all other participants should skip it also,
                    # as described in the docs
                    # so there is no need to mark as complete.
                    continue

                # save the participant, because tally_unvisited
                # queries index_in_pages directly from the DB
                self.participant.save()

                is_last, someone_waiting = page._tally_unvisited()
                if is_last and someone_waiting:
                    # the notify code uses self.request.build_absolute_uri
                    # to send the URL to the timeoutworker
                    page.request = self.request
                    page._run_aapa_and_notify(page._group_or_subsession)

    def is_displayed(self):
        return True

    def _update_monitor_table(self):
        participant = self.participant
        channel_utils.sync_group_send_wrapper(
            type='monitor_table_delta',
            group=channel_utils.session_monitor_group_name(participant._session_code),
            event=dict(rows=export.get_rows_for_monitor([participant])),
        )

    def _get_next_page_index_if_skipping_apps(self):
        # don't run it if the page is not displayed, because:
        # (1) it's consistent with other functions like before_next_page, vars_for_template
        # (2) then when we do
        # a lookahead skipping pages, we would need to check each page if it
        # has app_after_this_page defined, then set attributes and run it.
        # what if we are already skipping to a future app, then another page
        # has app_after_this_page? does it override the first one?
        if not self._is_displayed():
            return
        app_after_this_page = getattr(self, 'app_after_this_page', None)
        if not app_after_this_page:
            return

        current_app = self.participant._current_app_name
        app_sequence = self.session.config['app_sequence']
        current_app_index = app_sequence.index(current_app)
        upcoming_apps = app_sequence[current_app_index + 1 :]

        app_to_skip_to = app_after_this_page(upcoming_apps)
        if app_to_skip_to:
            if app_to_skip_to not in upcoming_apps:
                msg = f'"{app_to_skip_to}" is not in the upcoming_apps list'
                raise InvalidAppError(msg)
            return get_min_idx_for_app(self.participant._session_code, app_to_skip_to)

    def _record_page_completion_time(self):
        now = int(time.time())
        participant = self.participant

        session_code = participant._session_code

        otree.common2.make_page_completion_row(
            view=self,
            app_name=self.player._meta.app_config.name,
            participant__id_in_session=participant.id_in_session,
            participant__code=participant.code,
            session_code=session_code,
            is_wait_page=0,
        )

        participant._last_page_timestamp = now

    _is_frozen = False

    _setattr_whitelist = {
        '_is_frozen',
        'object',
        'form',
        'timeout_happened',
        # i should send some of these through context
        '_remaining_timeout_seconds',
        'first_field_with_errors',
        'other_fields_with_errors',
        'debug_tables',
        '_round_number',
        'request',  # this is just used in a test case mock.
    }

    def __setattr__(self, attr: str, value):
        if self._is_frozen and not attr in self._setattr_whitelist:
            msg = (
                'You set the attribute "{}" on the page {}. '
                'Setting attributes on page instances is not permitted. '
            ).format(attr, self.__class__.__name__)
            raise AttributeError(msg)
        else:
            # super() is a bit slower but only gets run during __init__
            super().__setattr__(attr, value)

    def live_url(self):
        return channel_utils.live_path(
            participant_code=self.participant.code,
            page_name=type(self).__name__,
            page_index=self._index_in_pages,
            session_code=self.participant._session_code,
            live_method_name=self.live_method,
        )

    live_method = ''


class Page(FormPageOrInGameWaitPage):
    # if a model is not specified, use empty "StubModel"
    form_model = UndefinedFormModel
    form_fields = []

    def inner_dispatch(self):
        if self.request.method == 'POST':
            return self.post()
        return self.get()

    def browser_bot_stuff(self, response: TemplateResponse):
        if self.participant.is_browser_bot:

            if hasattr(response, 'render'):
                response.render()
            browser_bots.set_attributes(
                participant_code=self.participant.code,
                request_path=self.request.path,
                html=response.content.decode('utf-8'),
            )
            has_next_submission = browser_bots.enqueue_next_post_data(
                participant_code=self.participant.code
            )
            if has_next_submission:
                # this doesn't work because we also would need to do this on OutOfRange page.
                # sometimes the player submits the last page, especially during development.
                # if self._index_in_pages == self.participant._max_page_index:
                auto_submit_js = '''
                <script>
                    var form = document.querySelector('#form');
                    form.submit();
                    // browser-bot-auto-submit
                    form.on('submit', function (e) {
                        e.preventDefault();
                    });
                </script>
                '''
                response.content += auto_submit_js.encode('utf8')
            else:
                browser_bots.send_completion_message(
                    session_code=self.participant._session_code,
                    participant_code=self.participant.code,
                )

    def get(self):
        if not self._is_displayed():
            self._increment_index_in_pages()
            return self._redirect_to_page_the_user_should_be_on()

        # this needs to be set AFTER scheduling submit_expired_url,
        # to prevent race conditions.
        # see that function for an explanation.
        self.participant._current_form_page_url = self.request.path
        self.object = self.get_object()

        self._update_monitor_table()

        # 2020-07-10: maybe we should call vars_for_template before instantiating the form
        # so that you can set initial value for a field in vars_for_template?
        form = self.get_form(instance=self.object)
        context = self.get_context_data(form=form)
        response = self.render_to_response(context)
        self.browser_bot_stuff(response)
        return response

    def get_template_names(self):
        if self.template_name is not None:
            return [self.template_name]
        return [
            '{}/{}.html'.format(
                get_app_label_from_import_path(self.__module__), self.__class__.__name__
            )
        ]

    def get_form_fields(self):
        return self.form_fields

    def _get_form_model(self):
        form_model = self.form_model
        if isinstance(form_model, str):
            if form_model == 'player':
                return self.PlayerClass
            if form_model == 'group':
                return self.GroupClass
            msg = (
                "'{}' is an invalid value for form_model. "
                "Try 'player' or 'group' instead.".format(form_model)
            )
            raise ValueError(msg)
        return form_model

    def get_form_class(self):
        try:
            fields = self.get_form_fields()
        except:
            raise ResponseForException
        form_model = self._get_form_model()
        if form_model is UndefinedFormModel and fields:
            msg = 'Page "{}" defined form_fields but not form_model'.format(
                self.__class__.__name__
            )
            raise Exception(msg)
        return django.forms.models.modelform_factory(
            form_model, fields=fields, form=otree.forms.ModelForm
        )

    def before_next_page(self):
        pass

    def get_form(self, data=None, files=None, **kwargs):
        """Given `data` and `files` QueryDicts, and optionally other named
        arguments, and returns a form.
        """

        cls = self.get_form_class()
        return cls(data=data, files=files, view=self, **kwargs)

    def form_invalid(self, form):
        context = self.get_context_data(form=form)

        fields_with_errors = [fname for fname in form.errors if fname != '__all__']

        # i think this should be before we call render_to_response
        # because the view (self) is passed to the template and rendered
        if fields_with_errors:
            self.first_field_with_errors = fields_with_errors[0]
            self.other_fields_with_errors = fields_with_errors[1:]

        response = self.render_to_response(context)
        response[
            otree.constants.redisplay_with_errors_http_header
        ] = otree.constants.get_param_truth_value

        return response

    def post(self):
        request = self.request

        self.object = self.get_object()

        if self.participant.is_browser_bot:
            submission = browser_bots.pop_enqueued_post_data(
                participant_code=self.participant.code
            )
            # convert MultiValueKeyDict to regular dict
            # so that we can add entries to it in a simple way
            # before, we used dict(request.POST), but that caused
            # errors with BooleanFields with blank=True that were
            # submitted empty...it said [''] is not a valid value
            post_data = request.POST.dict()
            post_data.update(submission)
        else:
            post_data = request.POST

        form = self.get_form(data=post_data, files=request.FILES, instance=self.object)
        self.form = form

        auto_submitted = post_data.get(otree.constants.timeout_happened)

        # if the page doesn't have a timeout_seconds, only the timeoutworker
        # should be able to auto-submit it.
        # otherwise users could append timeout_happened to the URL to skip pages
        has_secret_code = (
            post_data.get(otree.constants.admin_secret_code) == ADMIN_SECRET_CODE
        )

        # todo: make sure users can't change the result by removing 'timeout_happened'
        # from URL
        if auto_submitted and (has_secret_code or self.has_timeout_()):
            self.timeout_happened = True  # for public API
            self._process_auto_submitted_form(form)
        else:
            self.timeout_happened = False
            is_bot = self.participant._is_bot
            if form.is_valid():
                if is_bot and post_data.get('must_fail'):
                    msg = (
                        'Page "{}": Bot tried to submit intentionally invalid '
                        'data with '
                        'SubmissionMustFail, but it passed validation anyway:'
                        ' {}.'.format(
                            self.__class__.__name__, bot_prettify_post_data(post_data)
                        )
                    )
                    raise BotError(msg)
                # assigning to self.object is not really necessary
                self.object = form.save()
            else:
                if is_bot:
                    PageName = self.__class__.__name__
                    if not post_data.get('must_fail'):
                        errors = [
                            "{}: {}".format(k, repr(v)) for k, v in form.errors.items()
                        ]
                        msg = (
                            'Page "{}": Bot submission failed form validation: {} '
                            'Check your bot code, '
                            'then create a new session. '
                            'Data submitted was: {}'.format(
                                PageName, errors, bot_prettify_post_data(post_data)
                            )
                        )
                        raise BotError(msg)
                    if post_data.get('error_fields'):
                        # need to convert to dict because MultiValueKeyDict
                        # doesn't properly retrieve values that are lists
                        post_data_dict = dict(post_data)
                        expected_error_fields = set(post_data_dict['error_fields'])
                        actual_error_fields = set(form.errors.keys())
                        if not expected_error_fields == actual_error_fields:
                            msg = (
                                'Page {}, SubmissionMustFail: '
                                'Expected error_fields were {}, but actual '
                                'error_fields are {}'.format(
                                    PageName, expected_error_fields, actual_error_fields
                                )
                            )
                            raise BotError(msg)
                response = self.form_invalid(form)
                self.browser_bot_stuff(response)
                return response
        try:
            self.before_next_page()
        except Exception as exc:
            # why not raise ResponseForException?
            return response_for_exception(self.request, exc)
        self._record_page_completion_time()
        self._increment_index_in_pages()
        return self._redirect_to_page_the_user_should_be_on()

    def get_object(self):
        Cls = self._get_form_model()
        if Cls == self.GroupClass:
            return self.group
        if Cls == self.PlayerClass:
            return self.player
        if Cls == UndefinedFormModel:
            return UndefinedFormModel.objects.all()[0]

    def socket_url(self):
        '''called from template. can't start with underscore because used
        in template
        '''
        return channel_utils.auto_advance_path(
            participant_code=self.participant.code, page_index=self._index_in_pages
        )

    def redirect_url(self):
        '''called from template'''
        # need full path because we use query string
        return self.request.get_full_path()

    def _get_timeout_submission(self):
        timeout_submission = self.timeout_submission or {}
        for field_name in self.get_form_fields():
            if field_name not in timeout_submission:
                # get default value for datatype if the user didn't specify

                ModelClass = self._get_form_model()
                ModelField = ModelClass._meta.get_field(field_name)
                # TODO: should we warn if the attribute doesn't exist?
                value = getattr(ModelField, 'auto_submit_default', None)
                timeout_submission[field_name] = value
        return timeout_submission

    def _process_auto_submitted_form(self, form):
        '''
        # an empty submitted form looks like this:
        # {'f_currency': None, 'f_bool': None, 'f_int': None, 'f_char': ''}
        '''
        timeout_submission = self._get_timeout_submission()

        # force the form to be cleaned
        form.is_valid()

        has_non_field_error = form.errors.pop('__all__', False)

        # In a non-timeout form, error_message is only run if there are no
        # field errors (because the error_message function assumes all fields exist)
        # however, if there is a timeout, we accept the form even if there are some field errors,
        # so we have to make sure we don't skip calling error_message()
        if form.errors and not has_non_field_error:
            if hasattr(self, 'error_message'):
                try:
                    has_non_field_error = bool(self.error_message(form.cleaned_data))
                except:
                    has_non_field_error = True

        if has_non_field_error:
            # non-field errors exist.
            # ignore form, use timeout_submission entirely
            auto_submit_values_to_use = timeout_submission
        elif form.errors:
            auto_submit_values_to_use = {}
            for field_name in form.errors:
                auto_submit_values_to_use[field_name] = timeout_submission[field_name]
            form.errors.clear()
            form.save()
        else:
            auto_submit_values_to_use = {}
            form.save()
        for field_name in auto_submit_values_to_use:
            setattr(self.object, field_name, auto_submit_values_to_use[field_name])

    def has_timeout_(self):
        participant = self.participant
        return (
            participant._timeout_page_index == participant._index_in_pages
            and participant._timeout_expiration_time is not None
        )

    # don't use lru_cache. it is a global cache
    # @cached_property only in python 3.8
    _remaining_timeout_seconds = 'unset'

    def remaining_timeout_seconds(self):
        if self._remaining_timeout_seconds == 'unset':
            self._remaining_timeout_seconds = self.remaining_timeout_seconds_inner()
        return self._remaining_timeout_seconds

    def remaining_timeout_seconds_inner(self):
        current_time = time.time()
        participant = self.participant
        if participant._timeout_page_index == participant._index_in_pages:
            if participant._timeout_expiration_time is None:
                return None
            return participant._timeout_expiration_time - current_time
        try:
            timeout_seconds = self.get_timeout_seconds()
        except:
            raise ResponseForException
        participant._timeout_page_index = participant._index_in_pages
        if timeout_seconds is None:
            participant._timeout_expiration_time = None
            return None
        participant._timeout_expiration_time = current_time + timeout_seconds

        if otree.common.USE_TIMEOUT_WORKER:
            # if using browser bots, don't schedule the timeout,
            # because if it's a short timeout, it could happen before
            # the browser bot submits the page. Because the timeout
            # doesn't query the botworker (it is distinguished from bot
            # submits by the timeout_happened flag), it will "skip ahead"
            # and therefore confuse the bot system.
            if not self.participant.is_browser_bot:
                otree.tasks.submit_expired_url(
                    participant_code=self.participant.code,
                    path=self.request.path,
                    # add some seconds to account for latency of request + response
                    # this will (almost) ensure
                    # (1) that the page will be submitted by JS before the
                    # timeoutworker, which ensures that self.request.POST
                    # actually contains a value.
                    # (2) that the timeoutworker doesn't accumulate a lead
                    # ahead of the real page, which could result in being >1
                    # page ahead. that means that entire pages could be skipped
                    delay=timeout_seconds + 6,
                )
        return timeout_seconds

    def get_timeout_seconds(self):
        return self.timeout_seconds

    timeout_seconds = None
    timeout_submission = None
    timer_text = ugettext_lazy("Time left to complete this page:")


class GenericWaitPageMixin:
    """used for in-game wait pages, as well as other wait-type pages oTree has
    (like waiting for session to be created, or waiting for players to be
    assigned to matches

    """

    request = None

    def redirect_url(self):
        '''called from template'''
        # need get_full_path because we use query string here
        return self.request.get_full_path()

    def get_template_names(self):
        '''built-in wait pages should not be overridable'''
        return ['otree/WaitPage.html']

    def _get_wait_page(self):
        self.participant.is_on_wait_page = True
        self._update_monitor_table()
        response = TemplateResponse(
            self.request, self.get_template_names(), self.get_context_data()
        )
        response[
            otree.constants.wait_page_http_header
        ] = otree.constants.get_param_truth_value
        return response

    # Translators: the default title of a wait page
    title_text = ugettext_lazy('Please wait')
    body_text = None

    def _get_default_body_text(self):
        '''
        needs to be a method because it could say
        "waiting for the other player", "waiting for the other players"...
        '''
        return ''

    def get_context_data(self):
        title_text = self.title_text
        body_text = self.body_text

        # could evaluate to false like 0
        if body_text is None:
            body_text = self._get_default_body_text()

        # default title/body text can be overridden
        # if user specifies it in vars_for_template
        return {'view': self, 'title_text': title_text, 'body_text': body_text}


class WaitPage(FormPageOrInGameWaitPage, GenericWaitPageMixin):
    """
    Wait pages during game play (i.e. checkpoints),
    where users wait for others to complete
    """

    wait_for_all_groups = False
    group_by_arrival_time = False

    def get_context_data(self):
        context = GenericWaitPageMixin.get_context_data(self)
        return FormPageOrInGameWaitPage.get_context_data(self, **context)

    def get_template_names(self):
        """fallback to otree/WaitPage.html, which is guaranteed to exist.
        the reason for the 'if' statement, rather than returning a list,
        is that if the user explicitly defined template_name, and that template
        does not exist, then we should not fail silently.
        (for example, the user forgot to add it to git)
        """
        if self.template_name:
            return [self.template_name]
        return ['global/WaitPage.html', 'otree/WaitPage.html']

    def inner_dispatch(self, *args, **kwargs):
        # necessary because queries are made directly from DB

        if self.wait_for_all_groups == True:
            resp = self.inner_dispatch_subsession()
        elif self.group_by_arrival_time:
            resp = self.inner_dispatch_gbat()
        else:
            resp = self.inner_dispatch_group()
        return resp

    def _run_aapa_and_notify(self, group_or_subsession):
        '''new design is that if anybody is waiting on the wait page, we run AAPA.
        If nobody is shown the wait page, we don't need to notify or even create a
        CompletedGroupWaitPage record.
        '''
        if self.wait_for_all_groups:
            group = None
        else:
            group = group_or_subsession

        if isinstance(self.after_all_players_arrive, str):
            aapa_method = getattr(group_or_subsession, self.after_all_players_arrive)
        else:
            wp: WaitPage = type(self)()
            wp.set_attributes_waitpage_clone(original_view=self)
            wp._group_for_wp_clone = group
            aapa_method = wp.after_all_players_arrive
        try:
            aapa_method()
        except:
            raise ResponseForException
        self._mark_completed_and_notify(group=group)

    def inner_dispatch_group(self):
        ## EARLY EXITS
        if CompletedGroupWaitPage.objects.filter(
            page_index=self._index_in_pages,
            group_id=self.player.group_id,
            session_id=self._session_pk,
        ).exists():
            return self._response_when_ready()
        is_displayed = self._is_displayed()
        is_last, someone_waiting = self._tally_unvisited()
        if is_displayed and not is_last:
            return self._get_wait_page()
        elif is_last and (someone_waiting or is_displayed):
            self._run_aapa_and_notify(self.group)
        return self._response_when_ready()

    def inner_dispatch_subsession(self):

        if CompletedSubsessionWaitPage.objects.filter(
            page_index=self._index_in_pages, session=self.session
        ).exists():
            return self._response_when_ready()

        is_displayed = self._is_displayed()
        is_last, someone_waiting = self._tally_unvisited()
        if is_displayed and not is_last:
            return self._get_wait_page()
        elif is_last and (someone_waiting or is_displayed):
            self._run_aapa_and_notify(self.subsession)
        return self._response_when_ready()

    def inner_dispatch_gbat(self):
        if CompletedGBATWaitPage.objects.filter(
            page_index=self._index_in_pages,
            id_in_subsession=self.group.id_in_subsession,
            session=self.session,
        ).exists():
            return self._response_when_ready()

        if not self._is_displayed():
            # in GBAT, either all players should skip a page, or none should.
            # we don't support some players skipping and others not.
            return self._response_when_ready()

        participant = self.participant

        participant._gbat_is_waiting = True
        participant._gbat_page_index = self._index_in_pages
        participant._gbat_grouped = False
        # _last_request_timestamp is already set in set_attributes,
        # but set it here just so we can guarantee
        participant._last_request_timestamp = time.time()
        # need to save it inside the lock (check-then-act)
        # also because it needs to be up to date for get_players_for_group
        # which gets this info from the DB
        participant.save()
        # make a clean copy for GBAT and AAPA
        # self.player and self.participant etc are undefined
        # and no objects are cached inside it
        # and it doesn't affect the current instance

        gbat_new_group = self.subsession._gbat_try_to_make_new_group(
            self._index_in_pages
        )

        if gbat_new_group:
            self._run_aapa_and_notify(gbat_new_group)
            # gbat_new_group may not include the current player!
            # maybe this will not work if i change the implementation
            # so that the player is cached,
            # but that's OK because it will be obvious it doesn't work.

            if participant._gbat_grouped:
                return self._response_when_ready()

        return self._get_wait_page()

    @property
    def _group_or_subsession(self):
        return self.subsession if self.wait_for_all_groups else self.group

    # this is needed because on wait pages, self.player doesn't exist.
    # usually oTree finds the group by doing self.player.group.
    _group_for_wp_clone = None

    @property
    def group(self):
        return self._group_for_wp_clone or super().group

    def _mark_page_completions(self, player_values):
        '''
        this is more accurate than page load,
        because the player may delay doing that,
        to make it look like they waited longer.
        '''
        app_name = self.player._meta.app_config.name
        session_code = self.participant._session_code

        for p in player_values:
            otree.common2.make_page_completion_row(
                view=self,
                app_name=app_name,
                participant__id_in_session=p['participant__id_in_session'],
                participant__code=p['participant__code'],
                session_code=session_code,
                is_wait_page=1,
            )

    def _mark_completed_and_notify(self, group: Optional[BaseGroup]):
        # if group is not passed, then it's the whole subsession
        # could be 2 people creating the record at the same time
        # in _increment_index_in_pages, so could end up creating 2 records
        # but it's not a problem.

        base_kwargs = dict(page_index=self._index_in_pages, session_id=self._session_pk)

        if self.wait_for_all_groups:
            CompletedSubsessionWaitPage.objects.create(**base_kwargs)
            obj = self.subsession
        elif self.group_by_arrival_time:
            CompletedGBATWaitPage.objects.create(
                **base_kwargs, id_in_subsession=group.id_in_subsession
            )
            obj = group
        else:
            CompletedGroupWaitPage.objects.create(**base_kwargs, group_id=group.id)
            obj = group

        player_values = obj.player_set.values(
            'participant__id_in_session', 'participant__code', 'participant__pk'
        )

        self._mark_page_completions(player_values)

        Participant.objects.filter(
            id__in=[p['participant__pk'] for p in player_values]
        ).update(_last_page_timestamp=time.time())

        # this can cause messages to get wrongly enqueued in the botworker
        if otree.common.USE_TIMEOUT_WORKER and not self.participant.is_browser_bot:
            participant_pks = [p['participant__pk'] for p in player_values]
            # 2016-11-15: we used to only ensure the next page is visited
            # if the next page has a timeout, or if it's a wait page
            # but this is not reliable because next page might be skipped anyway,
            # and we don't know what page will actually be shown next to the user.
            otree.tasks.ensure_pages_visited(
                participant_pks=participant_pks,
                delay=10,
            )

        if self.group_by_arrival_time:
            channel_utils.sync_group_send_wrapper(
                type='gbat_ready',
                group=channel_utils.gbat_group_name(**base_kwargs),
                event={},
            )
        else:
            if self.wait_for_all_groups:
                channels_group_name = channel_utils.subsession_wait_page_name(
                    **base_kwargs
                )
            else:
                channels_group_name = channel_utils.group_wait_page_name(
                    **base_kwargs, group_id=group.id
                )

            channel_utils.sync_group_send_wrapper(
                type='wait_page_ready', group=channels_group_name, event={}
            )

    def socket_url(self):
        session_pk = self._session_pk
        page_index = self._index_in_pages
        participant_id = self.participant.pk
        if self.group_by_arrival_time:
            return channel_utils.gbat_path(
                session_pk=session_pk,
                page_index=page_index,
                app_name=self.player._meta.app_config.name,
                participant_id=participant_id,
                player_id=self.player.id,
            )
        elif self.wait_for_all_groups:
            return channel_utils.subsession_wait_page_path(
                session_pk=session_pk,
                page_index=page_index,
                participant_id=participant_id,
            )
        else:
            return channel_utils.group_wait_page_path(
                session_pk=session_pk,
                page_index=page_index,
                participant_id=participant_id,
                group_id=self.player.group_id,
            )

    def _tally_unvisited(self):

        participant_ids = list(
            self._group_or_subsession.player_set.values_list(
                'participant__id', flat=True
            )
        )
        participants = Participant.objects.filter(id__in=participant_ids)
        session_code = self.participant._session_code

        visited = []
        unvisited = []
        for p in participants:
            [unvisited, visited][p._index_in_pages >= self._index_in_pages].append(p)

        # this is not essential to functionality.
        # just for the display in the Monitor tab.
        if len(unvisited) <= 3:
            if len(unvisited) == 0:
                note = ''
            else:
                note = ', '.join(p._numeric_label() for p in unvisited)

                for p in visited:
                    p._monitor_note = note
                    p.save()

            channel_utils.sync_group_send_wrapper(
                type='update_notes',
                group=channel_utils.session_monitor_group_name(session_code),
                event=dict(ids=[p.id_in_session for p in visited], note=note),
            )

        is_last = not bool(unvisited)
        someone_waiting = any(
            [
                p._index_in_pages == self._index_in_pages and p.is_on_wait_page
                for p in participants
            ]
        )
        return (is_last, someone_waiting)

    def is_displayed(self):
        return True

    def _response_when_ready(self):
        '''
        Before calling this function, the following must be satisfied:
        - The completion object exists
        OR
        - The player skips this page
        '''
        participant = self.participant
        participant.is_on_wait_page = False
        participant._monitor_note = None
        self._increment_index_in_pages()
        return self._redirect_to_page_the_user_should_be_on()

    def after_all_players_arrive(self):
        pass

    def _get_default_body_text(self):
        num_other_players = self._group_or_subsession.player_set.count() - 1
        if num_other_players > 1:
            return _('Waiting for the other participants.')
        if num_other_players == 1:
            return _('Waiting for the other participant.')
        return ''


class AdminSessionPageMixin:
    @classmethod
    def url_pattern(cls):
        return r"^{}/(?P<code>[a-z0-9]+)/$".format(cls.__name__)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(
            session=self.session,
            is_debug=settings.DEBUG,
            request=self.request,
            **kwargs,
        )
        # vars_for_template has highest priority
        context.update(self.vars_for_template())
        return context

    def vars_for_template(self):
        '''
        simpler to use vars_for_template, but need to use get_context_data when:
        -   you need access to the context produced by the parent class,
            such as the form
        '''
        return {}

    def get_template_names(self):
        return ['otree/admin/{}.html'.format(self.__class__.__name__)]

    def dispatch(self, request, code, **kwargs):
        self.session = get_object_or_404(otree.models.Session, code=code)
        return super().dispatch(request, **kwargs)


class InvalidAppError(Exception):
    pass


REST_KEY_NAME = 'OTREE_REST_KEY'
REST_KEY_HEADER = 'otree-rest-key'


@method_decorator(csrf_exempt, name='dispatch')
class BaseRESTView(vanilla.View):
    def post(self, request):
        # hack to force plain text 500 page (Django checks .is_ajax())
        request.META['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        if settings.AUTH_LEVEL in ['DEMO', 'STUDY']:
            REST_KEY = os.getenv(REST_KEY_NAME)  # put it here for easy testing
            if not REST_KEY:
                return HttpResponseForbidden(
                    f'Env var {REST_KEY_NAME} must be defined to use REST API'
                )
            submitted_rest_key = request.headers.get(REST_KEY_HEADER)
            if not submitted_rest_key:
                return HttpResponseForbidden(
                    f'HTTP Request Header {REST_KEY_HEADER} is missing'
                )
            if REST_KEY != submitted_rest_key:
                return HttpResponseForbidden(
                    f'HTTP Request Header {REST_KEY_HEADER} is incorrect'
                )
        payload = json.loads(request.body.decode("utf-8"))
        return self.inner_post(**payload)

    def inner_post(self, **kwargs):
        raise NotImplementedError
