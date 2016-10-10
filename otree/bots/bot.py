#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import decimal
import logging
import abc
from importlib import import_module

import six
from six.moves import urllib
from six.moves.html_parser import HTMLParser

from django import test
from django.core.urlresolvers import resolve
from django.conf import settings
from easymoney import Money as Currency

from otree import constants_internal

from otree.common_internal import get_dotted_name, get_bots_module


logger = logging.getLogger('otree.bots')

DISABLE_CHECK_HTML_INSTRUCTIONS = '''
Checking the HTML may not find all form fields and buttons
(e.g. those added with JavaScript),
so you can disable this check by yielding a Submission
with check_html=False, e.g.:

yield Submission(views.PageName, {{...}}, check_html=False)
'''

HTML_MISSING_BUTTON_WARNING = ('''
Bot is trying to submit page {page_name},
but no button was not found in the HTML of the page.
(searched for <input> with type='submit' or <button> with type != 'button').
''' + DISABLE_CHECK_HTML_INSTRUCTIONS).replace('\n', ' ').strip()

HTML_MISSING_FIELD_WARNING = ('''
Bot is trying to submit page {page_name} with fields: "{fields}",
but these form fields were not found in the HTML of the page
(searched for tags {tags} with name= attribute matching the field name).
''' + DISABLE_CHECK_HTML_INSTRUCTIONS).replace('\n', ' ').strip()

class BOTS_CHECK_HTML:
    pass

def SubmitInternal(submission_tuple, check_html=BOTS_CHECK_HTML):

    if check_html == BOTS_CHECK_HTML:
        check_html = settings.BOTS_CHECK_HTML

    post_data = {}

    if isinstance(submission_tuple, (list, tuple)):
        PageClass = submission_tuple[0]
        if len(submission_tuple) == 2:
            post_data = submission_tuple[1]
    else:
        PageClass = submission_tuple

    post_data = post_data or {}

    # easy way to check if it's a wait page, without any messy imports
    if hasattr(PageClass, 'wait_for_all_groups'):
        raise AssertionError(
            "Your bot yielded '{}', which is a wait page. "
            "You should delete this line, because bots handle wait pages "
            "automatically."
        )

    for key in post_data:
        if isinstance(post_data[key], Currency):
            # because must be json serializable for Huey
            post_data[key] = str(decimal.Decimal(post_data[key]))

    return {
        'page_class': PageClass,
        'page_class_dotted': get_dotted_name(PageClass),
        'post_data': post_data,
        'check_html': check_html
    }


def Submission(
        PageClass, post_data=None, *, check_html=BOTS_CHECK_HTML):
    return SubmitInternal((PageClass, post_data), check_html)


def SubmissionMustFail(
        PageClass, post_data=None, *, check_html=BOTS_CHECK_HTML):
    '''lets you intentionally submit with invalid
    input to ensure it's correctly rejected'''

    post_data = post_data or {}

    # make a copy because we will mutate the input
    post_data = post_data.copy()

    # must_fail needs to go in post_data rather than being a separate
    # dict key, because CLI bots and browser bots need to work the same way.
    # CLI bots can only talk to server through post data
    post_data['must_fail'] = True

    return Submission(PageClass, post_data, check_html)


def normalize_html_whitespace(html):
    html = html.replace('\n', ' ').replace('\r', ' ')
    html = re.sub(r'\s+', ' ', html)
    return html

class HtmlString(str):

    def truncated(self):
        '''
        Make output more readable by truncating everything before the
         {% content %} block. I also considered indenting the HTML,
         but minidom had a parse error, and BS4 modifies a lot of tags,
         didn't seem optimal.
        '''
        div_str = '<div id="otree-content">'
        i = self.index(div_str) + len(div_str)
        return '...' + self[i:]

    def __str__(self):
        return self.truncated()

    def __repr__(self):
        return self.truncated()

# inherit from object for Python2.7 support.
# otherwise, get
class PageHtmlChecker(HTMLParser, object):

    def __init__(self, fields_to_check):
        super(PageHtmlChecker, self).__init__()
        self.missing_fields = set(fields_to_check)
        self.field_tags = {'input', 'button', 'select', 'textarea'}
        self.submit_button_found = False

    def get_missing_fields(self, html):
        self.feed(html)
        return self.missing_fields

    def check_if_field(self, tag, attrs):
        if tag in self.field_tags:
            for (attr_name, attr_value) in attrs:
                if attr_name == 'name':
                    self.missing_fields.discard(attr_value)

    def check_if_button(self, tag, attrs):
        if not self.submit_button_found:
            if tag == 'button':
                for (attr_name, attr_value) in attrs:
                    if attr_name == 'type' and attr_value == 'button':
                        return
                self.submit_button_found = True
            if tag == 'input':
                for (attr_name, attr_value) in attrs:
                    if attr_name == 'type' and attr_value == 'submit':
                        self.submit_button_found = True

    def handle_starttag(self, tag, attrs):
        self.check_if_field(tag, attrs)
        self.check_if_button(tag, attrs)


def is_wait_page(response):
    return (
        response.get(constants_internal.wait_page_http_header) ==
        constants_internal.get_param_truth_value)


def refresh_from_db(obj):
    return type(obj).objects.get(pk=obj.pk)


class ParticipantBot(six.with_metaclass(abc.ABCMeta, test.Client)):

    def __init__(
            self, participant, load_player_bots=True, **kwargs):
        self.participant = participant
        self.url = None
        self._response = None
        self._html = None
        self.path = None
        self.submits = None
        super(ParticipantBot, self).__init__()

        self.player_bots = []

        # load_player_bots can be set to False when it's convenient for
        # internal testing
        if load_player_bots:
            for player in self.participant.get_players():
                bots_module = get_bots_module(player._meta.app_config.name)
                player_bot = bots_module.PlayerBot(
                    player=player,
                    participant_bot=self)
                self.player_bots.append(player_bot)
            self.submits_generator = self.get_submits()

    def open_start_url(self):
        self.response = self.get(
            self.participant._start_url(),
            follow=True
        )

    def get_submits(self):
        for player_bot in self.player_bots:
            # play_round populates legacy submit list
            generator = player_bot.play_round()
            if player_bot._legacy_submit_list:
                for submission in player_bot._legacy_submit_list:
                    yield submission
            else:
                try:
                    for submission in generator:
                        if not isinstance(submission, dict):
                            submission = SubmitInternal(submission)
                        self.assert_correct_page(submission)
                        self.assert_html_ok(submission)
                        yield submission
                # handle the case where it's empty
                except TypeError as exc:
                    if 'is not iterable' in str(exc):
                        # we used to raise StopIteration here. But shouldn't
                        # do that, because then the whole participant bot
                        # stops running (e.g. doesn't play any of the
                        # PlayerBots in the following apps).
                        # this was causing a bug where we got "bot completed"
                        # but the bot had only played half the game
                        pass
                    else:
                        raise

    def assert_html_ok(self, submission):
        if submission['check_html']:
            field_names = [
                f for f in submission['post_data'].keys() if f != 'must_fail']
            checker = PageHtmlChecker(field_names)
            missing_fields = checker.get_missing_fields(self.html)
            if missing_fields:
                page_name = submission['page_class'].url_name()
                raise AssertionError(
                    HTML_MISSING_FIELD_WARNING.format(
                        page_name=page_name,
                        fields=', '.join(missing_fields),
                        tags=', '.join('<{}>'.format(tag)
                                       for tag in checker.field_tags)))
            if not checker.submit_button_found:
                page_name = submission['page_class'].url_name()
                raise AssertionError(HTML_MISSING_BUTTON_WARNING.format(
                    page_name=page_name))

    def assert_correct_page(self, submission):
        PageClass = submission['page_class']
        expected_url = PageClass.url_name()
        actual_url = resolve(self.path).url_name

        if not expected_url == actual_url:
            raise AssertionError(
                "Bot expects to be on page {}, "
                "but current page is {}. "
                "Check your bot in tests.py, "
                "then create a new session.".format(expected_url, actual_url))

    @property
    def response(self):
        return self._response

    @response.setter
    def response(self, response):
        try:
            self.url = response.redirect_chain[-1][0]
        except IndexError as exc:
            # this happens e.g. if you use SubmissionMustFail
            # and it returns the same URL
            pass
        else:
            self.path = urllib.parse.urlsplit(self.url).path
        self._response = response
        self.html = response.content.decode('utf-8')

    @property
    def html(self):
        return self._html

    @html.setter
    def html(self, html):
        self._html = HtmlString(normalize_html_whitespace(html))

    def on_wait_page(self):
        # if the existing response was a form page, it will still be...
        # no need to check again
        if not is_wait_page(self.response):
            return False

        # however, wait pages can turn into regular pages, so let's try again
        self.response = self.get(self.url, follow=True)
        return is_wait_page(self.response)

    def submit(self, submission):
        post_data = submission['post_data']
        if post_data:
            logger.info('{}, {}'.format(self.path, post_data))
        else:
            logger.info(self.path)

        self.response = self.post(self.url, post_data, follow=True)


class PlayerBot(object):

    cases = []

    def __init__(self, player, participant_bot, **kwargs):

        self.participant_bot = participant_bot
        self._cached_player = player
        self._cached_group = player.group
        self._cached_subsession = player.subsession
        self._cached_participant = player.participant
        self._cached_session = player.session
        self._legacy_submit_list = []

        case_number = self._cached_session._bot_case_number
        cases = self.cases
        if len(cases) >= 1:
            self.case = cases[case_number % len(cases)]
        else:
            self.case = None

    def play_round(self):
        pass

    @property
    def player(self):
        return refresh_from_db(self._cached_player)

    @property
    def group(self):
        return refresh_from_db(self._cached_group)

    @property
    def subsession(self):
        return refresh_from_db(self._cached_subsession)

    @property
    def session(self):
        return refresh_from_db(self._cached_session)

    @property
    def participant(self):
        return refresh_from_db(self._cached_participant)

    def submit(self, ViewClass, param_dict=None):
        self._legacy_submit_list.append(
            SubmitInternal((ViewClass, param_dict), check_html=False))

    def submit_invalid(self, ViewClass, param_dict=None):
        # simpler to make this a no-op, it makes porting to yield easier
        # then we can just do a search-and-replace
        # self._legacy_submit_list.append((ViewClass, param_dict, 'invalid'))
        pass

    @property
    def html(self):
        return self.participant_bot.html
