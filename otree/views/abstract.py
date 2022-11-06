import inspect
import logging
import time
import typing
from html import escape
from pathlib import Path
from typing import List
from typing import Optional

import starlette.exceptions
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData as StarletteFormData
from starlette.requests import Request
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.types import Receive, Scope, Send

# this is an expensive import
import otree.bots.browser as browser_bots
import otree.channels.utils as channel_utils
import otree.common
import otree.common2
import otree.constants
from otree.currency import json_dumps
import otree.forms
import otree.models
import otree.tasks
import otree.views.cbv
from otree import settings
from otree.bots.bot import bot_prettify_post_data
from otree.common import (
    get_app_label_from_import_path,
    get_dotted_name,
    get_admin_secret_code,
    DebugTable,
    BotError,
    NON_FIELD_ERROR_KEY,
    get_constants,
)
from otree.database import db, dbq
from otree.forms.forms import get_form
from otree.i18n import core_gettext
from otree.lookup import get_min_idx_for_app, get_page_lookup
from otree.models import Participant, Session, BaseGroup, BaseSubsession
from otree.models_concrete import (
    CompletedSubsessionWaitPage,
    CompletedGroupWaitPage,
    CompletedGBATWaitPage,
)
from otree.templating import render

logger = logging.getLogger(__name__)


ADMIN_SECRET_CODE = get_admin_secret_code()


BOT_COMPLETE_HTML_MESSAGE = '''
<html>
    <head>
        <title>Bot completed</title>
    </head>
    <body>Bot completed</body>
</html>
'''


class FormPageOrInGameWaitPage:
    request: Request

    @classmethod
    def instantiate_without_request(cls):
        return cls({'type': 'http'}, None, None)

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "http"
        self.scope = scope
        self.receive = receive
        self.send = send

    def __await__(self) -> typing.Generator:
        return self.dispatch().__await__()

    def call_user_defined(self, method_name, *args, **kwargs):
        """
        the default user-defined methods should not reference self, so they can work
        both as Player methods and Page methods.
        """
        if self.is_noself:
            return getattr(type(self), method_name)(self.player, *args, **kwargs)
        return getattr(self, method_name)(*args, **kwargs)

    async def dispatch(self) -> None:
        self.request = request = Request(self.scope, receive=self.receive)
        participant_code = request.path_params['participant_code']
        msg = (
            "This user does not exist in the database. " "Maybe the database was reset."
        )
        participant = db.get_or_404(Participant, code=participant_code, msg=msg)

        # if the player tried to skip past a part of the subsession
        # (e.g. by typing in a future URL)
        # or if they hit the back button to a previous subsession
        # in the sequence.
        url_should_be_on = participant._url_i_should_be_on()
        if not request.url.path == url_should_be_on:
            response = RedirectResponse(url_should_be_on, status_code=302)
        else:
            self.set_attributes(participant)
            # need to await the form from async function, otherwise run into complicated RuntimeError
            try:
                if request.method == 'POST':
                    self._form_data = await self.request.form()
            except starlette.requests.ClientDisconnect:
                # just make an empty response, to avoid
                # "RuntimeError: No response returned"
                response = starlette.responses.Response()
            else:
                response = await run_in_threadpool(self.inner_dispatch, request)
        await response(self.scope, self.receive, self.send)

    template_name = None

    is_debug = settings.DEBUG

    def inner_dispatch(self, request):
        '''inner dispatch function'''
        raise NotImplementedError()

    def get_template_name(self):
        raise NotImplementedError()

    @classmethod
    def url_pattern(cls, name_in_url):
        p = '/p/{participant_code}/%s/%s/{page_index}' % (name_in_url, cls.__name__)
        return p

    @classmethod
    def get_url(cls, participant_code, name_in_url, page_index):
        '''need this because reverse() is too slow in create_session'''
        # if i change this URL pattern, i should also change assert_correct_page()
        # in bot.py
        return f'/p/{participant_code}/{name_in_url}/{cls.__name__}/{page_index}'

    @classmethod
    def url_name(cls):
        '''using dots seems not to work'''
        return get_dotted_name(cls).replace('.', '-')

    def _redirect_to_page_the_user_should_be_on(self):
        return RedirectResponse(self.participant._url_i_should_be_on(), status_code=302)

    def get_context_data(self, **context):
        context.update(
            view=self,
            object=getattr(self, 'object', None),
            player=self.player,
            group=self.group,
            subsession=self.subsession,
            session=self.session,
            participant=self.participant,
            timer_text=getattr(self, 'timer_text', None),
            current_page_name=self.__class__.__name__,
            has_live_method=bool(getattr(self, 'live_method', None)),
        )

        Constants = self._Constants
        # it could be called C or Constants
        context[Constants.__name__] = Constants

        vars_for_template = {}

        user_vars = self.call_user_defined('vars_for_template')
        user_vars = user_vars or {}
        if not isinstance(user_vars, dict):
            raise Exception('vars_for_template did not return a dict')

        js_vars = self.call_user_defined('js_vars')

        try:
            # better to convert to json here so we can catch any errors,
            # rather than applying the filter in the template.
            context['js_vars'] = json_dumps(js_vars)
        except TypeError as exc:
            raise TypeError(f'js_vars contains an invalid value; {exc}') from None

        vars_for_template.update(user_vars)

        context.update(vars_for_template)

        if settings.DEBUG:
            self.debug_tables = self._get_debug_tables(vars_for_template)
        return context

    def render_to_response(self, context):
        return render(
            self.get_template_name(), context, template_type=self._template_type
        )

    _template_type = None

    def vars_for_template(self):
        return {}

    def js_vars(self):
        return {}

    def _get_debug_tables(self, vars_for_template):

        tables = []
        if vars_for_template:
            # use repr() so that we can distinguish strings from numbers
            # and can see currency types, etc.
            items = [(k, escape(repr(v))) for (k, v) in vars_for_template.items()]
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
        return self.call_user_defined('is_displayed')

    @property
    def group(self) -> BaseGroup:
        '''can't cache self._group_pk because group can change'''
        return self.player.group

    @property
    def subsession(self) -> BaseSubsession:
        '''so that it doesn't rely on player'''
        # this goes through idmap cache, so no perf hit
        return self.SubsessionClass.objects_get(id=self._subsession_pk)

    @property
    def session(self) -> Session:
        return Session.objects_get(id=self._session_pk)

    def set_attributes(self, participant):

        lookup = get_page_lookup(participant._session_code, participant._index_in_pages)
        self._lookup = lookup

        app_name = lookup.app_name

        models_module = otree.common.get_models_module(app_name)

        self._Constants = get_constants(app_name)
        self.PlayerClass = getattr(models_module, 'Player')
        self.GroupClass = getattr(models_module, 'Group')
        self.SubsessionClass = getattr(models_module, 'Subsession')
        self.player = self.PlayerClass.objects_get(
            participant=participant, round_number=lookup.round_number
        )
        self._subsession_pk = lookup.subsession_id
        self.round_number = lookup.round_number
        self._session_pk = lookup.session_pk
        # simpler if we set it directly so that we can do tests without idmap cache
        self._participant_pk = participant.id
        # setting it directly makes testing easier (tests dont need to use cache)
        self.participant: Participant = participant

        # it's already validated that participant is on right page
        self._index_in_pages = participant._index_in_pages

        # for the participant changelist
        participant._current_app_name = app_name
        participant._current_page_name = self.__class__.__name__
        participant._last_request_timestamp = int(time.time())
        participant._round_number = lookup.round_number

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
        participant = self.participant
        assert self._index_in_pages == participant._index_in_pages

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
            participant._max_page_index + 2,
        ):
            participant._index_in_pages = page_index
            if page_index == participant._max_page_index + 1:
                # break and go to OutOfRangeNotification
                break
            if is_skipping_apps and page_index == page_index_to_skip_to:
                break

            # scope, receive, send
            page = get_page_lookup(
                participant._session_code, page_index
            ).page_class.instantiate_without_request()

            page.set_attributes(self.participant)
            if not is_skipping_apps and page._is_displayed():
                break

            # if it's a wait page, record that they visited
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
                db.commit()

                is_last, someone_waiting = page._tally_unvisited()
                if is_last and someone_waiting:
                    page._run_aapa_and_notify(page._group_or_subsession)

    def is_displayed(self):
        return True

    def _update_monitor_table(self):
        self.participant._update_monitor_table()

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
        if not hasattr(self, 'app_after_this_page'):
            return

        current_app = self.participant._current_app_name
        app_sequence = self.session.config['app_sequence']
        current_app_index = app_sequence.index(current_app)
        upcoming_apps = app_sequence[current_app_index + 1 :]

        app_to_skip_to = self.call_user_defined('app_after_this_page', upcoming_apps)
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
            app_name=self.player.get_folder_name(),
            participant__id_in_session=participant.id_in_session,
            participant__code=participant.code,
            session_code=session_code,
            is_wait_page=0,
        )

        participant._last_page_timestamp = now

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
    form_model = None
    form_fields = []

    _template_type = 'Page'

    def inner_dispatch(self, request):
        if request.method == 'POST':
            return self.post()
        return self.get()

    def browser_bot_stuff(self, response: HTMLResponse):
        """we use this hack of appending to the HTML, rather than sending a context var,
        because we don't know if we need to submit the page until we try enqueueing the next post data.
        i guess that can't be done until we have the HTML of the page.
        """
        if self.participant.is_browser_bot:
            browser_bots.set_attributes(
                participant_code=self.participant.code,
                request_path=self.request.url.path,
                html=response.body.decode('utf-8'),
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
                extra_content = auto_submit_js.encode('utf8')
                response.body += extra_content
                response.headers['Content-Length'] = str(
                    int(response.headers['Content-Length']) + len(extra_content)
                )
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
        # self.participant._current_form_page_url = self.request.url.path

        self._update_monitor_table()

        # 2020-07-10: maybe we should call vars_for_template before instantiating the form
        # so that you can set initial value for a field in vars_for_template?
        # No, i don't want to commit to that.
        if self.has_form():
            obj = self.get_object()
            form = self.get_form(instance=obj)
        else:
            form = MockForm()

        context = self.get_context_data(form=form)
        response = self.render_to_response(context)
        self.browser_bot_stuff(response)
        return response

    def get_template_name(self):
        if self.template_name is not None:
            return self.template_name
        return '{}/{}.html'.format(
            get_app_label_from_import_path(self.__module__), self.__class__.__name__
        )

    def has_form(self):
        return bool(self._get_form_fields())

    def _get_form_fields(self):
        if hasattr(self, 'get_form_fields'):
            return self.call_user_defined('get_form_fields')
        return self.form_fields

    def get_object(self):
        if not self.form_model:
            msg = 'Page has form_fields but not form_model'
            raise Exception(msg)
        return {
            'player': self.player,
            'group': self.group,
            self.PlayerClass: self.player,
            self.GroupClass: self.group,
        }[self.form_model]

    def get_form(self, instance, formdata=None) -> otree.forms.forms.ModelForm:
        fields = self._get_form_fields()
        form = get_form(instance, field_names=fields, view=self, formdata=formdata)
        return form

    def form_invalid(self, form):
        context = self.get_context_data(form=form)

        fields_with_errors = [
            fname for fname in form.errors if fname != NON_FIELD_ERROR_KEY
        ]

        # i think this should be before we call render_to_response
        # because the view (self) is passed to the template and rendered
        if fields_with_errors:
            self.first_field_with_errors = fields_with_errors[0]
            self.other_fields_with_errors = fields_with_errors[1:]

        response = self.render_to_response(context)
        response.headers[
            otree.constants.redisplay_with_errors_http_header
        ] = otree.constants.get_param_truth_value

        return response

    def _check_submission_must_fail(self, is_bot, post_data):
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

    def post_handle_form(self, post_data):
        obj = self.get_object()
        form = self.get_form(formdata=post_data, instance=obj)
        self.form = form

        if self.timeout_happened:
            self._process_auto_submitted_form(form, obj)
        else:
            is_bot = self.participant._is_bot
            if form.validate():
                self._check_submission_must_fail(is_bot, post_data)
                form.populate_obj(obj)
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
                        expected_error_fields = set(post_data.getlist('error_fields'))
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

    _form_data = None

    def post(self):
        post_data = self._form_data
        auto_submitted = post_data.get(otree.constants.timeout_happened)
        # if the page doesn't have a timeout_seconds, only the timeoutworker
        # should be able to auto-submit it.
        # otherwise users could append timeout_happened to the URL to skip pages
        has_secret_code = (
            post_data.get(otree.constants.admin_secret_code) == ADMIN_SECRET_CODE
        )
        # convert it to a bool so that you can do e.g.
        # player.timeout_happened = timeout_happened
        self.timeout_happened = bool(
            auto_submitted and (has_secret_code or self._is_past_timeout())
        )
        if self.participant.is_browser_bot:
            submission = browser_bots.pop_enqueued_post_data(
                participant_code=self.participant.code
            )

            d = dict(post_data)
            # normalize to string because wtforms gets confused when it receives
            # string input, for example the int 0 does not pass InputRequired
            # (but how about CLI bots?)
            d.update({k: str(v) for k, v in submission.items()})
            post_data = StarletteFormData(d)

        if self.has_form():
            resp = self.post_handle_form(post_data)
            if resp:
                return resp
        elif hasattr(self, 'error_message') and not self.timeout_happened:
            # if the page has no form, we should still run error_message.
            # this is useful for live pages.
            # the code here is a stripped-down version of what happens with forms.
            is_bot = self.participant._is_bot
            error_message = self.call_user_defined('error_message', {})
            if error_message:
                if is_bot and not post_data.get('must_fail'):
                    msg = (
                        'Page "{}": Bot submission failed form validation: {} '
                        'Check your bot code, '
                        'then create a new session. '
                    ).format(self.__class__.__name__, error_message)
                    raise BotError(msg)
                context = self.get_context_data(
                    form=MockForm(error_message=error_message)
                )
                response = self.render_to_response(context)
                response.headers[
                    otree.constants.redisplay_with_errors_http_header
                ] = otree.constants.get_param_truth_value
                self.browser_bot_stuff(response)
                return response
            elif is_bot and post_data.get('must_fail'):
                self._check_submission_must_fail(is_bot, post_data)

        extra_args = (
            dict(timeout_happened=self.timeout_happened) if self.is_noself else {}
        )
        self.call_user_defined('before_next_page', **extra_args)
        self._record_page_completion_time()
        self._increment_index_in_pages()
        return self._redirect_to_page_the_user_should_be_on()

    def before_next_page(self, timeout_happened=False):
        pass

    def socket_url(self):
        '''called from template. can't start with underscore because used
        in template
        '''
        return channel_utils.auto_advance_path(
            participant_code=self.participant.code, page_index=self._index_in_pages
        )

    def _get_timeout_submission(self):
        '''timeout_submission is deprecated'''
        timeout_submission = self.timeout_submission or {}
        for field_name in self._get_form_fields():
            if field_name not in timeout_submission:
                # get default value for datatype if the user didn't specify
                ModelClass = type(self.get_object())
                value = getattr(ModelClass, field_name).auto_submit_default
                timeout_submission[field_name] = value
        return timeout_submission

    def _process_auto_submitted_form(self, form, obj):
        '''
        # an empty submitted form looks like this:
        # {'f_currency': None, 'f_bool': None, 'f_int': None, 'f_char': ''}
        '''
        timeout_submission = self._get_timeout_submission()

        # force the form to be cleaned
        form.validate()

        has_non_field_error = form.non_field_error

        # If there is a timeout, we accept whatever fields don't have errors,
        # so if there are errors, we have to call error_message manually,
        # since error_message is only run if there are no
        # field errors (because the error_message function assumes all fields exist)
        if form.errors and not has_non_field_error:
            if hasattr(self, 'error_message'):
                try:
                    has_non_field_error = bool(
                        self.call_user_defined('error_message', form.data)
                    )
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
            # save the fields without errors. we will overwrite the other fields with timeout_submission.
            form.errors.clear()
            form.populate_obj(obj)
        else:
            auto_submit_values_to_use = {}
            form.populate_obj(obj)
        for field_name in auto_submit_values_to_use:
            setattr(obj, field_name, auto_submit_values_to_use[field_name])

    def _is_past_timeout(self):
        """
        Need to check that we are actually past the expiration time.
        Otherwise, a participant could skip past a page before it's ready,
        by bypassing the execution of error_message(),
        which is skipped when there is a timeout.
        """
        pp = self.participant
        # the 2 seconds should not be necessary but there may be some unexpected case.
        return (
            pp._timeout_page_index == pp._index_in_pages
            and pp._timeout_expiration_time is not None
            and (pp._timeout_expiration_time - time.time() < 2)
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
        if hasattr(self, 'get_timeout_seconds'):
            timeout_seconds = self.call_user_defined('get_timeout_seconds')
        else:
            timeout_seconds = self.timeout_seconds
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
                    page_index=self.participant._index_in_pages,
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

    timeout_seconds = None
    timeout_submission = None
    timer_text = core_gettext("Time left to complete this page:")


class GenericWaitPageMixin:
    """used for in-game wait pages, as well as other wait-type pages oTree has
    (like waiting for session to be created, or waiting for players to be
    assigned to matches

    """

    request: Request = None

    def get_template_name(self):
        '''built-in wait pages should not be overridable'''
        return 'otree/WaitPage.html'

    def _get_wait_page(self):
        self.participant.is_on_wait_page = True
        self._update_monitor_table()
        response = render(self.get_template_name(), self.get_context_data())
        response.headers[
            otree.constants.wait_page_http_header
        ] = otree.constants.get_param_truth_value
        return response

    # Translators: the default title of a wait page
    title_text = core_gettext('Please wait')
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
        return dict(view=self, title_text=title_text, body_text=body_text)


class WaitPage(FormPageOrInGameWaitPage, GenericWaitPageMixin):
    """
    Wait pages during game play (i.e. checkpoints),
    where users wait for others to complete
    """

    wait_for_all_groups = False
    group_by_arrival_time = False

    _template_type = 'WaitPage'

    def get_context_data(self):
        context = GenericWaitPageMixin.get_context_data(self)
        return FormPageOrInGameWaitPage.get_context_data(self, **context)

    def get_template_name(self):
        """fallback to otree/WaitPage.html, which is guaranteed to exist.
        the reason for the 'if' statement, rather than returning a list,
        is that if the user explicitly defined template_name, and that template
        does not exist, then we should not fail silently.
        (for example, the user forgot to add it to git)
        """
        if self.template_name:
            return self.template_name

        if Path('_templates/global/WaitPage.html').exists():
            return 'global/WaitPage.html'
        return 'otree/WaitPage.html'

    def inner_dispatch(self, request):
        # we need inner_dispatch() for common interface w/ parent class
        # and .get() so it can be called explicitly.
        return self.get()

    def get(self):
        # necessary because queries are made directly from DB

        if self.wait_for_all_groups == True:
            resp = self.inner_dispatch_subsession()
        elif self.group_by_arrival_time:
            resp = self.inner_dispatch_gbat()
        else:
            resp = self.inner_dispatch_group()
        return resp

    def _run_aapa_and_notify(self, group_or_subsession):
        '''
        group_or_subsession is passed explicitly, because in the case of GBAT it might
        not include the current player, so we can't just use self.player.group.

        new design is that if anybody is waiting on the wait page, we run AAPA.
        If nobody is shown the wait page, we don't need to notify or even create a
        CompletedGroupWaitPage record.
        '''
        if self.wait_for_all_groups:
            group = None
            noself_kwargs = dict(subsession=group_or_subsession)
        else:
            group = group_or_subsession
            noself_kwargs = dict(group=group_or_subsession)

        aapa = type(self).after_all_players_arrive
        if isinstance(aapa, str):
            group_or_subsession.call_user_defined(aapa)
        # old format; it's a regular method
        elif str(inspect.signature(aapa)) == '(self)':
            wp: WaitPage = type(self)({'type': 'http'}, None, None)
            wp.set_attributes_waitpage_clone(original_view=self)
            wp._group_for_wp_clone = group
            wp.after_all_players_arrive()
        else:
            # noself
            # pass kwargs so that we can ensure the user did not use a group method
            # where a subsession method should have been used
            aapa(**noself_kwargs)
        self._mark_completed_and_notify(group=group)

    def inner_dispatch_group(self):
        ## EARLY EXITS
        if CompletedGroupWaitPage.objects_exists(
            page_index=self._index_in_pages,
            group_id=self.player.group_id,
            session_id=self._session_pk,
        ):
            return self._response_when_ready()
        is_displayed = self._is_displayed()
        is_last, someone_waiting = self._tally_unvisited()
        if is_displayed and not is_last:
            return self._get_wait_page()
        elif is_last and (someone_waiting or is_displayed):
            self._run_aapa_and_notify(self.group)
        return self._response_when_ready()

    def inner_dispatch_subsession(self):

        if CompletedSubsessionWaitPage.objects_exists(
            page_index=self._index_in_pages, session=self.session
        ):
            return self._response_when_ready()

        is_displayed = self._is_displayed()
        is_last, someone_waiting = self._tally_unvisited()
        if is_displayed and not is_last:
            return self._get_wait_page()
        elif is_last and (someone_waiting or is_displayed):
            self._run_aapa_and_notify(self.subsession)
        return self._response_when_ready()

    def inner_dispatch_gbat(self):
        if CompletedGBATWaitPage.objects_exists(
            page_index=self._index_in_pages,
            id_in_subsession=self.group.id_in_subsession,
            session=self.session,
        ):
            return self._response_when_ready()

        if not self._is_displayed():
            # in GBAT, either all players should skip a page, or none should.
            # we don't support some players skipping and others not.
            return self._response_when_ready()

        participant = self.participant

        participant._gbat_is_connected = True
        participant._gbat_page_index = self._index_in_pages
        participant._gbat_grouped = False
        # _last_request_timestamp is already set in set_attributes,
        # but set it here just so we can guarantee
        participant._last_request_timestamp = int(time.time())
        # need to save it inside the lock (check-then-act)
        # also because it needs to be up to date for get_players_for_group
        # which gets this info from the DB
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

    def _get_participants_for_this_waitpage(self, group_or_subsession):
        """
        group_or_subsession needs to be passed because it could be a newly created group with GBAT,
        and may not equal self.group because the current player may not be part of the group.
        (for example, when creating single-player groups with waiting_too_long).
        """
        Player = self.PlayerClass
        fk_field = Player.subsession_id if self.wait_for_all_groups else Player.group_id
        # tried select_from but my filter clause didn't work
        return (
            dbq(Player)
            .join(Participant)
            .filter(fk_field == group_or_subsession.id)
            .with_entities(Participant)
        )

    # this is needed because on wait pages, self.player doesn't exist.
    # usually oTree finds the group by doing self.player.group.
    _group_for_wp_clone = None

    @property
    def group(self):
        return self._group_for_wp_clone or super().group

    def _mark_page_completions(self, participants: List[Participant]):
        '''
        this is more accurate than page load,
        because the player may delay doing that,
        to make it look like they waited longer.
        '''
        app_name = self.player.get_folder_name()
        session_code = self.participant._session_code

        for pp in participants:
            otree.common2.make_page_completion_row(
                view=self,
                app_name=app_name,
                participant__id_in_session=pp.id_in_session,
                participant__code=pp.code,
                session_code=session_code,
                is_wait_page=1,
            )

    def _mark_completed_and_notify(self, group: Optional[BaseGroup]):
        # if group is not passed, then it's the whole subsession
        # could be 2 people creating the record at the same time
        # in _increment_index_in_pages, so could end up creating 2 records
        # but it's not a problem.

        base_kwargs = dict(page_index=self._index_in_pages, session_id=self._session_pk)
        Player = self.PlayerClass

        if self.wait_for_all_groups:
            CompletedSubsessionWaitPage.objects_create(**base_kwargs)
        elif self.group_by_arrival_time:
            db.add(
                CompletedGBATWaitPage(
                    **base_kwargs, id_in_subsession=group.id_in_subsession
                )
            )
        else:
            db.add(CompletedGroupWaitPage(**base_kwargs, group_id=group.id))

        participants = self._get_participants_for_this_waitpage(
            group or self.subsession
        )
        self._mark_page_completions(list(participants))
        for pp in participants:
            pp._last_page_timestamp = int(time.time())

        # this can cause messages to get wrongly enqueued in the botworker
        if otree.common.USE_TIMEOUT_WORKER and not self.participant.is_browser_bot:
            # 2016-11-15: we used to only ensure the next page is visited
            # if the next page has a timeout, or if it's a wait page
            # but this is not reliable because next page might be skipped anyway,
            # and we don't know what page will actually be shown next to the user.
            otree.tasks.ensure_pages_visited(
                participant_pks=[pp.id for pp in participants],
                delay=10,
                page_index=self._index_in_pages,
            )

        if self.group_by_arrival_time:
            channel_utils.sync_group_send(
                group=channel_utils.gbat_group_name(**base_kwargs),
                data={'status': 'ready'},
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

            channel_utils.sync_group_send(
                group=channels_group_name, data={'status': 'ready'}
            )

    def socket_url(self):
        session_pk = self._session_pk
        page_index = self._index_in_pages
        participant_id = self.participant.id
        if self.group_by_arrival_time:
            return channel_utils.gbat_path(
                session_pk=session_pk,
                page_index=page_index,
                app_name=self.player.get_folder_name(),
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

        participants = self._get_participants_for_this_waitpage(
            self._group_or_subsession
        )
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

            channel_utils.sync_group_send(
                group=channel_utils.session_monitor_group_name(session_code),
                data=dict(
                    ids=[p.id_in_session for p in visited],
                    note=note,
                    type='update_notes',
                ),
            )

        # is_last is not technically true. maybe someone else also is waiting for this page
        # just behind you. but it doesn't matter; you can still advance the waitpage.
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
            return core_gettext('Waiting for the other participants.')
        if num_other_players == 1:
            return core_gettext('Waiting for the other participant.')
        return ''


class InvalidAppError(Exception):
    pass


class MockForm:
    def __iter__(self):
        if False:
            yield

    def __init__(self, error_message=None):
        self.non_field_error = error_message

    field_names = []

    @property
    def errors(self):
        return bool(self.non_field_error)
