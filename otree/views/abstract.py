from django.core import signals
from django.core.exceptions import (
    PermissionDenied, SuspiciousOperation,
)
from django.http.multipartparser import MultiPartParserError
from django.urls import get_resolver, get_urlconf

import contextlib
import importlib
import json
import logging
import time

import channels
import otree.channels.utils as channel_utils
import redis_lock
import vanilla
from django.conf import settings
from django.core.urlresolvers import resolve
from django.db.models import Max
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.decorators.cache import never_cache, cache_control
import idmap
import otree.common_internal
import otree.constants_internal as constants
import otree.db.idmap
import otree.forms
import otree.models
import otree.timeout.tasks
from otree.bots.bot import bot_prettify_post_data
import otree.bots.browser as browser_bots
from otree.common_internal import (
    get_app_label_from_import_path, get_dotted_name, get_admin_secret_code,
    DebugTable, BotError, wait_page_thread_lock, ResponseForException
)
from otree.models import (
    Participant, Session, BasePlayer, BaseGroup, BaseSubsession)
from otree.models_concrete import (
    PageCompletion, CompletedSubsessionWaitPage,
    CompletedGroupWaitPage, PageTimeout, UndefinedFormModel,
    ParticipantLockModel,
)
from django.core.handlers.exception import handle_uncaught_exception


logger = logging.getLogger(__name__)


UNHANDLED_EXCEPTIONS = (
    Http404, PermissionDenied, MultiPartParserError,
    SuspiciousOperation, SystemExit
)

def response_for_exception(request, exc):
    '''simplified from Django 1.11 source.
    The difference is that we use the exception that was passed in,
    rather than referencing sys.exc_info(), which gives us the ResponseForException
    the original exception was wrapped in, which we don't want to show to users.
        '''
    if isinstance(exc, UNHANDLED_EXCEPTIONS):
        '''copied from Django 1.11 source, but i don't think these
        exceptions will actually occur.'''
        raise exc
    signals.got_request_exception.send(sender=None, request=request)
    exc_info = (type(exc), exc, exc.__traceback__)
    response = handle_uncaught_exception(
        request, get_resolver(get_urlconf()), exc_info)

    # Force a TemplateResponse to be rendered.
    if not getattr(response, 'is_rendered', True) and callable(getattr(response, 'render', None)):
        response = response.render()

    return response

NO_PARTICIPANTS_LEFT_MSG = (
    "The maximum number of participants for this session has been exceeded.")

ADMIN_SECRET_CODE = get_admin_secret_code()


def get_view_from_url(url):
    view_func = resolve(url).func
    module = importlib.import_module(view_func.__module__)
    Page = getattr(module, view_func.__name__)
    return Page


@contextlib.contextmanager
def participant_scoped_db_lock(participant_code):
    '''
    prevent the same participant from executing the page twice
    use this instead of a transaction because it's more lightweight.
    transactions make it harder to reason about wait pages
    '''
    TIMEOUT = 10
    start_time = time.time()
    while time.time() - start_time < TIMEOUT:
        updated_locks = ParticipantLockModel.objects.filter(
            participant_code=participant_code,
            locked=False
        ).update(locked=True)
        if not updated_locks:
            time.sleep(0.2)
        else:
            try:
                yield
            finally:
                ParticipantLockModel.objects.filter(
                    participant_code=participant_code,
                ).update(locked=False)
            return
    exists = ParticipantLockModel.objects.filter(
        participant_code=participant_code
    ).exists()
    if not exists:
        raise Http404((
            "This user ({}) does not exist in the database. "
            "Maybe the database was recreated."
        ).format(participant_code))

    # could happen if the request that has the lock is paused somehow,
    # e.g. in a debugger
    raise Exception(
        'Another HTTP request has the lock for participant {}.'.format(
            participant_code))


def get_redis_lock(*, name='global'):
    if otree.common_internal.USE_REDIS:
        return redis_lock.Lock(
            redis_client=otree.common_internal.get_redis_conn(),
            name='OTREE_LOCK_{}'.format(name),
            expire=10,
            auto_renewal=True
        )


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
            name_in_url,
            cls.__name__,
        )
        return p

    @classmethod
    def get_url(cls, participant_code, name_in_url, page_index):
        '''need this because reverse() is too slow in create_session'''
        return r'/p/{pcode}/{name_in_url}/{ClassName}/{page_index}/'.format(
            pcode=participant_code, name_in_url=name_in_url,
            ClassName=cls.__name__, page_index=page_index
        )

    @classmethod
    def url_name(cls):
        '''using dots seems not to work'''
        return get_dotted_name(cls).replace('.', '-')

    def _redirect_to_page_the_user_should_be_on(self):
        return HttpResponseRedirect(self.participant._url_i_should_be_on())

    @method_decorator(never_cache)
    @method_decorator(cache_control(must_revalidate=True, max_age=0,
                                    no_cache=True, no_store=True))
    def dispatch(self, *args, **kwargs):
        participant_code = kwargs.pop(constants.participant_code)

        if otree.common_internal.USE_REDIS:
            lock = redis_lock.Lock(
                otree.common_internal.get_redis_conn(),
                participant_code,
                expire=60,
                auto_renewal=True
            )
        else:
            lock = participant_scoped_db_lock(participant_code)

        with lock, otree.db.idmap.use_cache():
            try:
                participant = Participant.objects.get(
                    code=participant_code)
            except Participant.DoesNotExist:
                msg = (
                    "This user ({}) does not exist in the database. "
                    "Maybe the database was recreated."
                ).format(participant_code)
                raise Http404(msg)

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
            except ResponseForException as exc:
                response = response_for_exception(
                    self.request, exc.__cause__ or exc.__context__
                )
            except Exception as exc:
                # this is still necessary, e.g. if an attribute on the page
                # is invalid, like form_fields, form_model, etc.
                response = response_for_exception(self.request, exc)

            otree.db.idmap.save_objects()
            if self.participant.is_browser_bot:
                html = response.content.decode('utf-8')
                # 2018-04-25: not sure why i didn't use an HTTP header.
                # the if statement doesn't even seem to make a difference.
                # shouldn't it always submit, if we're in a Page class?
                # or why not just set an attribute directly on the response object?
                # OTOH, this is pretty guaranteed to work. whereas i'm not sure
                # that we can isolate the exact set of cases when we have to
                # add the auto-submit flag (only GET requests, not wait pages,
                # ...etc?)
                if 'browser-bot-auto-submit' in html:
                    # needs to happen in GET, so that we can set the .html
                    # attribute on the bot.
                    browser_bots.set_attributes(
                        participant_code=self.participant.code,
                        request_path=self.request.path,
                        html=html,
                    )
            return response

    def get_context_data(self, **context):

        context.update({
            'view': self,
            # 2017-08-22: why do we need this?
            'object': getattr(self, 'object', None),
            'player': self.player,
            'group': self.group,
            'subsession': self.subsession,
            'session': self.session,
            'participant': self.participant,
            'Constants': self._Constants,

            # doesn't exist on wait pages, so need getattr
            'timer_text': getattr(self, 'timer_text', None)
        })

        vars_for_template = {}
        views_module = otree.common_internal.get_pages_module(
            self.subsession._meta.app_config.name)
        if hasattr(views_module, 'vars_for_all_templates'):
            vars_for_template.update(views_module.vars_for_all_templates(self) or {})

        try:
            user_vars = self.vars_for_template()
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
            request=self.request,
            template=self.get_template_names(),
            context=context
        )

    def vars_for_template(self):
        return {}

    def _get_debug_tables(self, vars_for_template):
        try:
            group_id = self.group.id_in_subsession
        except:
            group_id = ''

        tables = []
        if vars_for_template:
            # use repr() so that we can distinguish strings from numbers
            # and can see currency types, etc.
            items = [(k, repr(v)) for (k, v) in vars_for_template.items()]
            rows = sorted(items)
            tables.append(DebugTable(title='Vars for template', rows=rows))

        basic_info_table = DebugTable(
            title='Basic info',
            rows=[
                ('ID in group', self.player.id_in_group),
                ('Group', group_id),
                ('Round number', self.subsession.round_number),
                ('Participant', self.player.participant._id_in_session()),
                ('Participant label', self.player.participant.label or ''),
                ('Session code', self.session.code)
            ]
        )

        tables.append(basic_info_table)

        return tables

    def _load_all_models(self):
        '''Load all model instances into idmap cache'''
        self.PlayerClass.objects.select_related(
            'group', 'subsession', 'session'
        ).get(pk=self._player_pk)

    def _is_displayed(self):
        try:
            is_displayed = self.is_displayed()
        except:
            raise ResponseForException
        if is_displayed is None:
            msg = (
                '{}: is_displayed() did not return anything. '
                'You should fix this. To show the page, you should return True; '
                'to skip the page, return False.'
            ).format(self.__class__.__name__)
            logger.warning(msg)
        return is_displayed

    @property
    def player(self) -> BasePlayer:
        # NOTE:
        # these properties look in the idmap cache, so they don't touch
        # the database if they are already loaded
        return self.PlayerClass.objects.get(pk=self._player_pk)

    @property
    def group(self) -> BaseGroup:
        '''can't cache self._group_pk because group can change'''
        return self.player.group

    @property
    def subsession(self) -> BaseSubsession:
        return self.SubsessionClass.objects.get(pk=self._subsession_pk)

    @property
    def participant(self) -> Participant:
        return Participant.objects.get(pk=self._participant_pk)

    @property
    def session(self) -> Session:
        return Session.objects.get(pk=self._session_pk)

    _round_number = None
    @property
    def round_number(self):
        if self._round_number is None:
            self._round_number = self.subsession.round_number
        return self._round_number

    def set_attributes(self, participant, lazy=False):

        player_lookup = participant.player_lookup()

        app_name = player_lookup['app_name']

        models_module = otree.common_internal.get_models_module(app_name)
        self._Constants = models_module.Constants
        self.PlayerClass = getattr(models_module, 'Player')
        self.GroupClass = getattr(models_module, 'Group')
        self.SubsessionClass = getattr(models_module, 'Subsession')
        self._player_pk = player_lookup['player_pk']
        self._subsession_pk = player_lookup['subsession_pk']
        self._session_pk = player_lookup['session_pk']
        self._participant_pk = participant.pk

        # it's already validated that participant is on right page
        self._index_in_pages = participant._index_in_pages

        # for the participant changelist
        participant._current_app_name = app_name
        participant._current_page_name = self.__class__.__name__
        participant._last_request_timestamp = time.time()

        if not lazy:
            self._load_all_models()
            self.participant._round_number = self.player.round_number

        self._is_frozen = True

    # python 3.5 type hint
    def set_attributes_waitpage_clone(self, *, original_view: 'WaitPage'):
        '''put it here so it can be compared with set_attributes...
        but this is really just a method on wait pages'''

        self._Constants = original_view._Constants
        self.PlayerClass = original_view.PlayerClass
        self.GroupClass = original_view.GroupClass
        self.SubsessionClass = original_view.SubsessionClass
        self._subsession_pk = original_view._subsession_pk
        self._session_pk = original_view._session_pk
        self._participant_pk = original_view._participant_pk

        # is this needed?
        self._index_in_pages = original_view._index_in_pages

    def _increment_index_in_pages(self):
        # when is this not the case?
        assert self._index_in_pages == self.participant._index_in_pages

        self._record_page_completion_time()
        # we should allow a user to move beyond the last page if it's mturk
        # also in general maybe we should show the 'out of sequence' page

        # we skip any page that is a sequence page where is_displayed
        # evaluates to False to eliminate unnecessary redirection

        for page_index in range(
                # go to max_page_index+2 because range() skips the last index
                # and it's possible to go to max_page_index + 1 (OutOfRange)
                self._index_in_pages+1, self.participant._max_page_index+2):
            self.participant._index_in_pages = page_index
            if page_index == self.participant._max_page_index+1:
                # break and go to OutOfRangeNotification
                break
            url = self.participant._url_i_should_be_on()

            Page = get_view_from_url(url)
            page = Page()

            page.set_attributes(self.participant, lazy=True)
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
                # this fixes a bug reported on 2016-11-04 on the mailing list
                self.participant.save()
                # you could just return page.dispatch(),
                # but that could cause deep recursion

                unvisited = page._get_unvisited_ids()
                if not unvisited:
                    # we don't run after_all_players_arrive()
                    page._mark_completed()
                    participant_pk_set = set(
                        page._group_or_subsession.player_set.values_list(
                            'participant__pk', flat=True))
                    page.send_completion_message(participant_pk_set)

    def is_displayed(self):
        return True

    def _record_page_completion_time(self):

        now = int(time.time())

        last_page_timestamp = self.participant._last_page_timestamp
        if last_page_timestamp is None:
            logger.warning(
                'Participant {}: _last_page_timestamp is None'.format(
                    self.participant.code))
            last_page_timestamp = now

        seconds_on_page = now - last_page_timestamp

        self.participant._last_page_timestamp = now
        page_name = self.__class__.__name__

        timeout_happened = bool(getattr(self, 'timeout_happened', False))

        PageCompletion.objects.create(
            app_name=self.subsession._meta.app_config.name,
            page_index=self._index_in_pages,
            page_name=page_name, time_stamp=now,
            seconds_on_page=seconds_on_page,
            subsession_pk=self.subsession.pk,
            participant=self.participant,
            session=self.session,
            auto_submitted=timeout_happened)
        self.participant.save()

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
        'request' # this is just used in a test case mock.
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

    def _force_setattr(self, attr: str, value):
        '''maybe better to use whitelist rather than this;
        that keeps all the code in 1 place'''
        orig = self._is_frozen
        self._is_frozen = False
        try:
            setattr(self, attr, value)
        finally:
            self._is_frozen = orig

class Page(FormPageOrInGameWaitPage):

    # if a model is not specified, use empty "StubModel"
    form_model = UndefinedFormModel
    form_fields = []

    def inner_dispatch(self):
        if self.request.method == 'POST':
            return self.post()
        return self.get()

    def get(self):
        if not self._is_displayed():
            self._increment_index_in_pages()
            return self._redirect_to_page_the_user_should_be_on()

        # this needs to be set AFTER scheduling submit_expired_url,
        # to prevent race conditions.
        # see that function for an explanation.
        self.participant._current_form_page_url = self.request.path
        self.object = self.get_object()
        form = self.get_form(instance=self.object)
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def get_template_names(self):
        if self.template_name is not None:
            return [self.template_name]
        return ['{}/{}.html'.format(
            get_app_label_from_import_path(self.__module__),
            self.__class__.__name__)]

    def get_form_fields(self):
        return self.form_fields

    def _get_form_model(self):
        form_model = self.form_model
        if isinstance(form_model, str):
            if form_model == 'player':
                return self.PlayerClass
            if form_model == 'group':
                return self.GroupClass
            raise ValueError(
                "'{}' is an invalid value for form_model. "
                "Try 'player' or 'group' instead.".format(form_model)
            )
        return form_model

    def get_form_class(self):
        try:
            fields = self.get_form_fields()
        except:
            raise ResponseForException
        if isinstance(fields, str):
            # it could also happen with get_form_fields,
            # but that is much less commonly used, so we word the error
            # message just about form_fields.
            msg = (
                'form_fields should be a list, not the string {fld}. '
                'Maybe you meant this: form_fields = [{fld}]'
            ).format(fld=repr(fields))
            raise ValueError(msg)
        form_model = self._get_form_model()
        if form_model is UndefinedFormModel and fields:
            raise Exception(
                'Page "{}" defined form_fields but not form_model'.format(
                    self.__class__.__name__
                )
            )
        return otree.forms.modelform_factory(
            form_model, fields=fields,
            form=otree.forms.ModelForm,
            formfield_callback=otree.forms.formfield_callback)

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

        fields_with_errors = [
            fname for fname in form.errors
            if fname != '__all__']

        # i think this should be before we call render_to_response
        # because the view (self) is passed to the template and rendered
        if fields_with_errors:
            self.first_field_with_errors = fields_with_errors[0]
            self.other_fields_with_errors = fields_with_errors[1:]

        response = self.render_to_response(context)
        response[constants.redisplay_with_errors_http_header] = (
            constants.get_param_truth_value)

        return response

    def post(self):
        request = self.request

        self.object = self.get_object()

        if self.participant.is_browser_bot:
            submission = browser_bots.get_next_post_data(
                participant_code=self.participant.code)
            if submission is None:
                browser_bots.send_completion_message(
                    session_code=self.session.code,
                    participant_code=self.participant.code
                )
                return HttpResponse(BOT_COMPLETE_HTML_MESSAGE)
            else:
                # convert MultiValueKeyDict to regular dict
                # so that we can add entries to it in a simple way
                # before, we used dict(request.POST), but that caused
                # errors with BooleanFields with blank=True that were
                # submitted empty...it said [''] is not a valid value
                post_data = request.POST.dict()
                post_data.update(submission)
        else:
            post_data = request.POST

        form = self.get_form(
                data=post_data, files=request.FILES, instance=self.object)
        self.form = form

        auto_submitted = request.POST.get(constants.timeout_happened)

        # if the page doesn't have a timeout_seconds, only the timeoutworker
        # should be able to auto-submit it.
        # otherwise users could append timeout_happened to the URL to skip pages
        has_secret_code = (
            request.POST.get(constants.admin_secret_code) == ADMIN_SECRET_CODE)

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
                    raise BotError(
                        'Page "{}": Bot tried to submit intentionally invalid '
                        'data with '
                        'SubmissionMustFail, but it passed validation anyway:'
                        ' {}.'.format(
                            self.__class__.__name__,
                            bot_prettify_post_data(post_data)))
                # assigning to self.object is not really necessary
                self.object = form.save()
            else:
                response = self.form_invalid(form)
                if is_bot:
                    PageName = self.__class__.__name__
                    if not post_data.get('must_fail'):
                        errors = [
                            "{}: {}".format(k, repr(v))
                            for k, v in form.errors.items()]
                        raise BotError(
                            'Page "{}": Bot submission failed form validation: {} '
                            'Check your bot in tests.py, '
                            'then create a new session. '
                            'Data submitted was: {}'.format(
                                PageName,
                                errors,
                                bot_prettify_post_data(post_data),
                            ))
                    if post_data.get('error_fields'):
                        # need to convert to dict because MultiValueKeyDict
                        # doesn't properly retrieve values that are lists
                        post_data_dict = dict(post_data)
                        expected_error_fields = set(post_data_dict['error_fields'])
                        actual_error_fields = set(form.errors.keys())
                        if not expected_error_fields == actual_error_fields:
                            raise BotError(
                                'Page {}, SubmissionMustFail: '
                                'Expected error_fields were {}, but actual '
                                'error_fields are {}'.format(
                                    PageName,
                                    expected_error_fields,
                                    actual_error_fields,
                                )
                            )
                return response
        try:
            self.before_next_page()
        except Exception as exc:
            return response_for_exception(self.request, exc)

        if self.participant.is_browser_bot:
            if self._index_in_pages == self.participant._max_page_index:
                # fixme: is it right to set html=''?
                # could this break any asserts?
                browser_bots.set_attributes(
                    participant_code=self.participant.code,
                    request_path=self.request.path,
                    html='',
                )
                submission = browser_bots.get_next_post_data(
                        participant_code=self.participant.code)
                if submission is None:
                    browser_bots.send_completion_message(
                        session_code=self.session.code,
                        participant_code=self.participant.code
                    )
                    return HttpResponse(BOT_COMPLETE_HTML_MESSAGE)
                else:
                    raise BotError(
                        'Finished the last page, '
                        'but the bot is still trying '
                        'to submit more data ({}).'.format(submission)
                    )
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
            participant_code=self.participant.code,
            page_index=self._index_in_pages
        )

    def redirect_url(self):
        '''called from template'''
        # need full path because we use query string
        return self.request.get_full_path()

    def _get_auto_submit_values(self):
        # TODO: auto_submit_values deprecated on 2015-05-28
        auto_submit_values = getattr(self, 'auto_submit_values', {})
        timeout_submission = self.timeout_submission or auto_submit_values
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
        auto_submit_values = self._get_auto_submit_values()

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
            auto_submit_values_to_use = auto_submit_values
        elif form.errors:
            auto_submit_values_to_use = {}
            for field_name in form.errors:
                auto_submit_values_to_use[field_name] = auto_submit_values[field_name]
            form.errors.clear()
            form.save()
        else:
            auto_submit_values_to_use = {}
            form.save()
        for field_name in auto_submit_values_to_use:
            setattr(self.object, field_name, auto_submit_values_to_use[field_name])

    def has_timeout_(self):
        return PageTimeout.objects.filter(
            participant=self.participant,
            page_index=self.participant._index_in_pages).exists()

    _remaining_timeout_seconds = 'unset'
    def remaining_timeout_seconds(self):

        if self._remaining_timeout_seconds is not 'unset':
            return self._remaining_timeout_seconds

        try:
            timeout_seconds = self.get_timeout_seconds()
        except:
            raise ResponseForException

        if timeout_seconds is None:
            # don't hit the DB at all
            pass
        else:
            current_time = time.time()
            expiration_time = current_time + timeout_seconds

            timeout_object, created = PageTimeout.objects.get_or_create(
                participant=self.participant,
                page_index=self.participant._index_in_pages,
                defaults={'expiration_time': expiration_time})

            timeout_seconds = timeout_object.expiration_time - current_time
            if created and otree.common_internal.USE_REDIS:
                # if using browser bots, don't schedule the timeout,
                # because if it's a short timeout, it could happen before
                # the browser bot submits the page. Because the timeout
                # doesn't query the botworker (it is distinguished from bot
                # submits by the timeout_happened flag), it will "skip ahead"
                # and therefore confuse the bot system.
                if not self.participant.is_browser_bot:
                    otree.timeout.tasks.submit_expired_url.schedule(
                        (
                            self.participant.code,
                            self.request.path,
                        ),
                        # add some seconds to account for latency of request + response
                        # this will (almost) ensure
                        # (1) that the page will be submitted by JS before the
                        # timeoutworker, which ensures that self.request.POST
                        # actually contains a value.
                        # (2) that the timeoutworker doesn't accumulate a lead
                        # ahead of the real page, which could result in being >1
                        # page ahead. that means that entire pages could be skipped

                        # task queue can't schedule tasks in the past
                        # at least 1 second from now
                        delay=max(1, timeout_seconds+8))
        self._remaining_timeout_seconds = timeout_seconds
        return timeout_seconds

    def get_timeout_seconds(self):
        return self.timeout_seconds

    timeout_seconds = None
    timeout_submission = None
    timer_text = ugettext_lazy("Time left to complete this page:")





_MSG_Undefined_GetPlayersForGroup = (
    'You cannot reference self.player, self.group, or self.participant '
    'inside get_players_for_group.'
)

_MSG_Undefined_AfterAllPlayersArrive_Player = (
    'self.player and self.participant cannot be referenced '
    'inside after_all_players_arrive, '
    'which is executed only once '
    'for the entire group.'
)

_MSG_Undefined_AfterAllPlayersArrive_Group = (
    'self.group cannot be referenced inside after_all_players_arrive '
    'if wait_for_all_groups=True, '
    'because after_all_players_arrive() is executed only once '
    'for all groups in the subsession.'
)

class Undefined_AfterAllPlayersArrive_Player:
    def __getattribute__(self, item):
        raise AttributeError(_MSG_Undefined_AfterAllPlayersArrive_Player)

    def __setattr__(self, item, value):
        raise AttributeError(_MSG_Undefined_AfterAllPlayersArrive_Player)


class Undefined_AfterAllPlayersArrive_Group:
    def __getattribute__(self, item):
        raise AttributeError(_MSG_Undefined_AfterAllPlayersArrive_Group)

    def __setattr__(self, item, value):
        raise AttributeError(_MSG_Undefined_AfterAllPlayersArrive_Group)


class Undefined_GetPlayersForGroup:

    def __getattribute__(self, item):
        raise AttributeError(_MSG_Undefined_GetPlayersForGroup)

    def __setattr__(self, item, value):
        raise AttributeError(_MSG_Undefined_GetPlayersForGroup)


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
        response = TemplateResponse(
            self.request, self.get_template_names(), self.get_context_data())
        response[constants.wait_page_http_header] = (
            constants.get_param_truth_value)
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
        return {
            'view': self,
            'title_text': title_text,
            'body_text': body_text,
        }


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
        ## EARLY EXITS
        if self._was_completed():
            return self._save_and_flush_and_response_when_ready()
        is_displayed = self._is_displayed()

        if self.group_by_arrival_time and not is_displayed:
            # in GBAT, either all players should skip a page, or none should.
            # we don't support some players skipping and others not.
            return self._response_when_ready()

        if is_displayed and not self.group_by_arrival_time:
            if self._get_unvisited_ids():
                self.participant.is_on_wait_page = True
                return self._get_wait_page()
        ## END EARLY EXITS

        with get_redis_lock(name='otree_waitpage') or wait_page_thread_lock:
            # setting myself to _gbat_arrived = True should happen inside the lock
            # because otherwise, another player might be able to see that I have arrived
            # before I can run get_players_for_group, and they might end up grouping
            # me. But because I am not in their group, they will not run AAPA for me
            # so I will be considered 'already_grouped' and redirected to a wait page,
            # and AAPA will never be run.

            # also, it's simpler in general to have a broad lock.
            # and easier to explain to users that it will be run as each player
            # arrives.

            if self.group_by_arrival_time:
                self.player._gbat_arrived = True
                # _last_request_timestamp is already set in set_attributes,
                # but set it here just so we can guarantee
                self.participant._last_request_timestamp = time.time()
                # we call save_objects() below

            otree.db.idmap.save_objects()
            idmap.flush()

            # make a clean copy for GBAT and AAPA
            # self.player and self.participant etc are undefined
            # and no objects are cached inside it
            # and it doesn't affect the current instance
            wp = type(self)() # type: WaitPage
            wp.set_attributes_waitpage_clone(original_view=self)


            # needs to happen before calculating participant_pk_set
            # because this can change the group or PK
            if wp.group_by_arrival_time:
                wp._player_access_forbidden = Undefined_GetPlayersForGroup()
                wp._participant_access_forbidden = Undefined_GetPlayersForGroup()
                wp._group_access_forbidden = Undefined_GetPlayersForGroup()

                # check if the player was already grouped.
                # this is a 'check' of the check-then-act, so it needs to be
                # inside the lock.
                # It's possible that the player
                # was grouped, but the Completion object does not exist yet,
                # because aapa was not run.
                already_grouped = type(self.player).objects.filter(
                    id=self.player.id).values_list(
                    '_gbat_grouped', flat=True)[0]
                if already_grouped:
                    regrouped = False
                else:
                    # 2017-10-29: what if the current player is not one
                    # of the people being regrouped?
                    regrouped = wp._gbat_try_to_regroup()

                if not regrouped:
                    self.participant.is_on_wait_page = True
                    return self._get_wait_page()

                wp._player_access_forbidden = None
                wp._participant_access_forbidden = None
                wp._group_access_forbidden = None

            # the group membership might be modified
            # in after_all_players_arrive, so calculate this first
            participant_pk_set = set(
                self._group_or_subsession.player_set
                .values_list('participant__pk', flat=True))

            if not self._was_completed():
                if is_displayed:
                    # if any player can skip the wait page,
                    # then we shouldn't run after_all_players_arrive
                    # because if some players are able to proceed to the next page
                    # before after_all_players_arrive is run,
                    # then after_all_players_arrive is probably not essential.
                    # often, there are some wait pages that all players skip,
                    # because they should only be shown in certain rounds.
                    # maybe the fields that after_all_players_arrive depends on
                    # are null
                    # something to think about: ideally, should we check if
                    # all players skipped, or any player skipped?
                    # as a shortcut, we just check if is_displayed is true
                    # for the last player.

                    wp._player_access_forbidden = Undefined_AfterAllPlayersArrive_Player()
                    wp._participant_access_forbidden = Undefined_AfterAllPlayersArrive_Player()
                    if wp.wait_for_all_groups:
                        wp._group_access_forbidden = Undefined_AfterAllPlayersArrive_Group()
                    else:
                        wp._group_access_forbidden = None
                        wp._group_for_aapa = self.group
                    try:
                        wp.after_all_players_arrive()
                    except:
                        raise ResponseForException
                    # need to save to the results of after_all_players_arrive
                    # to the DB, before sending the completion message to other players
                    # this was causing a race condition on 2016-11-04
                    otree.db.idmap.save_objects()
                # even if this player skips the page and after_all_players_arrive
                # is not run, we need to indicate that the waiting players can advance
                self._mark_completed()
                self.send_completion_message(participant_pk_set)
        return self._save_and_flush_and_response_when_ready()

    def _gbat_try_to_regroup(self):
        # if someone arrives within this many seconds of the last heartbeat of
        # a player who drops out, they will be stuck.
        # that sounds risky, but remember that
        # if a player drops out at any point after that,
        # the other players in the group will also be stuck.
        # so the purpose of this is not to prevent dropouts that happen
        # for random reasons, but specifically on a wait page,
        # which is usually because someone gets stuck waiting for a long time.
        # we don't want to make it too short, because that means the page
        # would have to refresh very quickly, which could be disruptive.
        STALE_THRESHOLD_SECONDS = 20

        # count how many are re-grouped
        waiting_players = list(self.subsession.player_set.filter(
            _gbat_arrived=True,
            _gbat_grouped=False,
            participant___last_request_timestamp__gte=time.time()-STALE_THRESHOLD_SECONDS
        ))

        try:
            players_for_group = self.get_players_for_group(waiting_players)
        except:
            raise ResponseForException

        if not players_for_group:
            return False
        participant_ids = [p.participant.id for p in players_for_group]

        group_id_in_subsession = self._gbat_next_group_id_in_subsession()

        Constants = self._Constants

        with otree.common_internal.transaction_except_for_sqlite():
            for round_number in range(self.round_number, Constants.num_rounds+1):
                subsession = self.subsession.in_round(round_number)

                unordered_players = subsession.player_set.filter(
                    participant_id__in=participant_ids)

                participant_ids_to_players = {
                    player.participant.id: player for player in unordered_players}

                ordered_players_for_group = [
                    participant_ids_to_players[participant_id]
                    for participant_id in participant_ids]

                if round_number == self.round_number:
                    for player in ordered_players_for_group:
                        player._gbat_grouped = True
                        player.save()

                group = self.GroupClass.objects.create(
                    subsession=subsession, id_in_subsession=group_id_in_subsession,
                    session=self.session, round_number=round_number)
                group.set_players(ordered_players_for_group)

                # prune groups without players
                # apparently player__isnull=True works, didn't know you could
                # use this in a reverse direction.
                subsession.group_set.filter(player__isnull=True).delete()
        return True

    def get_players_for_group(self, waiting_players):
        Constants = self._Constants

        if Constants.players_per_group is None:
            raise AssertionError(
                'Page "{}": if using group_by_arrival_time, you must either set '
                'Constants.players_per_group to a value other than None, '
                'or define get_players_for_group() on the page.'.format(
                    self.__class__.__name__
                )
            )

        if len(waiting_players) >= Constants.players_per_group:
            return waiting_players[:Constants.players_per_group]

    def _gbat_next_group_id_in_subsession(self):
        # 2017-05-05: seems like this can result in id_in_subsession that
        # doesn't start from 1.
        # especially if you do group_by_arrival_time in every round
        # is that a problem?
        res = self.GroupClass.objects.filter(
            session=self.session).aggregate(Max('id_in_subsession'))
        return res['id_in_subsession__max'] + 1

    _player_access_forbidden = None
    @property
    def player(self):
        return self._player_access_forbidden or super().player

    _group_access_forbidden = None
    _group_for_aapa = None
    @property
    def group(self):
        return self._group_access_forbidden or self._group_for_aapa or super().group

    _participant_access_forbidden = None
    @property
    def participant(self):
        return self._participant_access_forbidden or super().participant

    @property
    def _group_or_subsession(self):
        return self.subsession if self.wait_for_all_groups else self.group

    def _save_and_flush_and_response_when_ready(self):
        # need to deactivate cache, in case after_all_players_arrive
        # finished running after the moment set_attributes
        # was called in this request.

        # because in response_when_ready we will call
        # increment_index_in_pages, which does a look-ahead and calls
        # is_displayed() on the following pages. is_displayed() might
        # depend on a field that is set in after_all_players_arrive
        # so, need to clear the cache to ensure
        # that we get fresh data.

        # Note: i was never able to reproduce this myself -- just heard
        # from Anthony N.
        # and it shouldn't happen, because only the last player to visit
        # can set is_ready(). if there is a request coming after that,
        # then it must be someone refreshing the page manually.
        # i guess we should protect against that.

        # is_displayed() could also depend on a field on participant
        # that was set on the wait page, so need to refresh participant,
        # because it is passed as an arg to set_attributes().


        otree.db.idmap.save_objects()
        idmap.flush()
        return self._response_when_ready()

    def _was_completed(self):
        if self.wait_for_all_groups:
            return CompletedSubsessionWaitPage.objects.filter(
                page_index=self._index_in_pages,
                session=self.session,
            ).exists()
        return CompletedGroupWaitPage.objects.filter(
            page_index=self._index_in_pages,
            id_in_subsession=self.group.id_in_subsession,
            session=self.session,
        ).exists()

    def _mark_completed(self):
        # could be 2 people creating the record at the same time
        # in _increment_index_in_pages, so could end up creating 2 records
        # but it's not a problem.
        if self.wait_for_all_groups:
            CompletedSubsessionWaitPage.objects.create(
                page_index=self._index_in_pages,
                session=self.session
            )
        else:
            CompletedGroupWaitPage.objects.create(
                page_index=self._index_in_pages,
                id_in_subsession=self.group.id_in_subsession,
                session=self.session
            )

    def send_completion_message(self, participant_pk_set):

        if otree.common_internal.USE_REDIS:
            # 2016-11-15: we used to only ensure the next page is visited
            # if the next page has a timeout, or if it's a wait page
            # but this is not reliable because next page might be skipped anyway,
            # and we don't know what page will actually be shown next to the user.
            otree.timeout.tasks.ensure_pages_visited.schedule(
                kwargs={
                    'participant_pk_set': participant_pk_set},
                delay=10)

        # _group_or_subsession might be deleted
        # in after_all_players_arrive, but it won't delete the cached model
        channels_group_name = self.get_channels_group_name()
        channels.Group(channels_group_name).send(
            {'text': json.dumps(
                {'status': 'ready'})}
        )

    def _channels_group_id_in_subsession(self):
        if self.wait_for_all_groups:
            return ''
        return self.group.id_in_subsession

    def get_channels_group_name(self):
        if self.group_by_arrival_time:
            return self._gbat_get_channels_group_name()
        group_id_in_subsession = self._channels_group_id_in_subsession()

        return channel_utils.wait_page_group_name(
            session_pk=self._session_pk,
            page_index=self._index_in_pages,
            group_id_in_subsession=group_id_in_subsession)

    def socket_url(self):
        if self.group_by_arrival_time:
            return self._gbat_socket_url()

        group_id_in_subsession = self._channels_group_id_in_subsession()

        return channel_utils.wait_page_path(
            self._session_pk,
            self._index_in_pages,
            group_id_in_subsession
        )


    def _get_unvisited_ids(self):
        """
        Don't need a lock
        """

        participant_ids = set(
            self._group_or_subsession.player_set.values_list(
                'participant_id', flat=True))

        # essential query whose results can change from moment to moment
        participant_data = Participant.objects.filter(
            id__in=participant_ids
        ).values('id', 'id_in_session', '_index_in_pages')

        visited = []
        unvisited = []
        for p in participant_data:
            if p['_index_in_pages'] < self._index_in_pages:
                unvisited.append(p)
            else:
                visited.append(p)

        # this is not essential to functionality.
        # just for the display in the Monitor tab.
        # so, we don't need a lock, even though there could be a race condition.
        if 1 <= len(unvisited) <= 3:

            unvisited_description = ', '.join(
                'P{}'.format(p['id_in_session']) for p in unvisited)

            visited_ids = [p['id'] for p in visited]
            Participant.objects.filter(
                id__in=visited_ids
            ).update(_waiting_for_ids=unvisited_description)

        return {p['id'] for p in unvisited}

    def is_displayed(self):
        return True

    def _response_when_ready(self):
        '''
        Before calling this function, the following must be satisfied:
        - The completion object exists
        OR
        - The player skips this page
        '''
        self.participant.is_on_wait_page = False
        self.participant._waiting_for_ids = None
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

    ## THE REST OF THIS CLASS IS GROUP_BY_ARRIVAL_TIME STUFF


    def _gbat_get_channels_group_name(self):
            return channel_utils.gbat_group_name(
                session_pk=self._session_pk, page_index=self._index_in_pages,
            )

    def _gbat_socket_url(self):
        return channel_utils.gbat_path(
            self._session_pk, self._index_in_pages,
            self.player._meta.app_config.name, self.player.id)


class AdminSessionPageMixin:

    @classmethod
    def url_pattern(cls):
        return r"^{}/(?P<code>[a-z0-9]+)/$".format(cls.__name__)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'session': self.session,
            'is_debug': settings.DEBUG,
            'request': self.request,
        })
        return context

    def get_template_names(self):
        return ['otree/admin/{}.html'.format(self.__class__.__name__)]

    def dispatch(self, request, *args, **kwargs):
        session_code = kwargs['code']
        self.session = get_object_or_404(
            otree.models.Session, code=session_code)
        return super().dispatch(
            request, *args, **kwargs)

    def get_form_class(self):
        """A drop-in replacement for
        ``vanilla.model_views.GenericModelView.get_form_class``. The only
        difference is that we use oTree's modelform_factory in order to always
        get a floppyfied form back which supports richer widgets.
        """
        if self.form_class is not None:
            return self.form_class

        return otree.forms.modelform_factory(
            self.model,
            fields=self.fields,
            formfield_callback=otree.forms.formfield_callback)
