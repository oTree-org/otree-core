#!/usr/bin/env python

from __future__ import unicode_literals, division, print_function
from collections import OrderedDict, defaultdict
from fractions import gcd
from functools import reduce
try:
    from http.client import CannotSendRequest, BadStatusLine
except ImportError:  # Python 2.7
    from httplib import CannotSendRequest, BadStatusLine
import json
from math import ceil
import os
import platform
import re
from socket import socket
import sqlite3
from subprocess import call, Popen, PIPE, STDOUT, CalledProcessError, DEVNULL
from threading import Thread, local
from time import time, sleep
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse, resolve
from django.db import connection
from django.utils.formats import date_format
from django.utils.timezone import now
from huey.contrib.djhuey import HUEY
from psutil import Process, NoSuchProcess, virtual_memory
from selenium.common.exceptions import (
    NoSuchElementException, NoSuchWindowException
)
from selenium.webdriver import Chrome
from selenium.webdriver.support.select import Select
from tqdm import tqdm

from otree import __version__ as otree_version
from otree.models import Session, Participant
from otree.session import create_session, SESSION_CONFIGS_DICT
from otree.test.client import refresh_from_db


def is_port_available(host, port):
    return socket().connect_ex((host, port)) != 0


def notify(message):
    """
    Sends a global system notification so users can see a message
    without checking the program every 5 seconds.

    Works only on some Linux desktop systems like Ubuntu.
    """
    try:
        call(('notify-send', message))
    except OSError:
        pass


def lcm(values):
    """
    Least common multiple.
    """
    return int(reduce(lambda x, y: (x*y) / gcd(x, y), values, 1))


class Series:
    def __init__(self, graph, name):
        self.graph = graph
        self.name = name
        self.data = defaultdict(list)
        self.averages = OrderedDict()

    def time(self, x):
        series = self

        class Time:
            def __enter__(self):
                self.start = time()

            def __exit__(self, exc_type, exc_val, exc_tb):
                elapsed = time() - self.start
                series.add(x, elapsed)

        return Time()

    def add(self, x, y):
        if y is not None:
            self.data[x].append(y)
            self.set_average(x)

    def set_average(self, x):
        l = self.data[x].copy()
        self.averages[x] = sum(l) / len(l)

    def to_dict(self):
        return {'name': self.name,
                'data': list(self.averages.items())}


class Graph:
    template = """
    <div id="container-%(id)s" style="width: 800px; height: 400px;">
    </div>
    <script>
        $(function () {
            $('#container-%(id)s').highcharts({
                title: {
                    text: %(title)s,
                    x: -70 // compensates the legend width.
                },
                subtitle: {
                    text: %(subtitle)s,
                    x: -70 // compensates the legend width.
                },
                xAxis: {
                    title: {
                        text: %(x_title)s
                    },
                },
                yAxis: {
                    title: {
                        text: %(y_title)s
                    },
                    plotLines: [{
                        value: 0,
                        width: 1,
                        color: '#808080'
                    }]
                },
                tooltip: {
                    pointFormat: '{point.y:.2f} ' + %(y_unit)s
                },
                legend: {
                    layout: 'vertical',
                    align: 'right',
                    verticalAlign: 'middle',
                    borderWidth: 0
                },
                series: %(all_series)s
            });
        });
    </script>
    """

    def __init__(self, title, subtitle='', x_title='',
                 y_title='Time (s)', y_unit='s'):
        self.id = uuid.uuid4()
        self.title = title
        self.subtitle = subtitle
        self.x_title = x_title
        self.y_title = y_title
        self.y_unit = y_unit
        self.all_series = OrderedDict()

    def get_series(self, name):
        if name in self.all_series:
            return self.all_series[name]
        series = Series(self, name)
        self.all_series[name] = series
        return series

    def to_html(self):
        return self.template % {
            'id': self.id, 'title': json.dumps(self.title),
            'subtitle': json.dumps(self.subtitle),
            'x_title': json.dumps(self.x_title),
            'y_title': json.dumps(self.y_title),
            'y_unit': json.dumps(self.y_unit),
            'all_series': json.dumps([s.to_dict()
                                      for s in self.all_series.values()]),
        }


class Report:
    template = """
    <!DOCTYPE html>
    <html>
        <head>
            <style>
                dt {
                    font-weight: bold;
                }
            </style>
            <script src="https://code.jquery.com/jquery-2.2.4.min.js"></script>
            <script src="https://code.highcharts.com/highcharts.js"></script>
        </head>
        <body>
            <h1>Conditions</h1>
            Stress test started on %(datetime)s
            %(conditions)s

            <h1>Measures</h1>

            %(graphs)s
        </body>
    </html>
    """

    def __init__(self):
        self.graphs = OrderedDict()
        self.filename = 'stress_test_report.html'
        print('The report will be generated in %s' % self.filename)

        self.conditions = self.get_conditions()

    def get_conditions(self):
        versions = OrderedDict((
            ('oTree', otree_version),
            ('Python', platform.python_version()),
        ))

        # CPU
        cpuinfo_path = '/proc/cpuinfo'
        if os.path.exists(cpuinfo_path):
            # TODO: This works only on Linux.
            with open(cpuinfo_path) as f:
                versions['CPU'] = re.search(r'^model name\s+: (.+)$', f.read(),
                                            flags=re.MULTILINE).group(1)

        # RAM
        ram = virtual_memory().total
        GiB = 1 << 30
        versions['RAM'] = '%.2f GiB' % (ram / GiB)

        # OS
        linux_dist = ' '.join(platform.linux_distribution()).strip()
        if linux_dist:
            versions['Linux distribution'] = linux_dist
        else:
            versions['OS'] = platform.system() + ' ' + platform.release()

        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                db_engine = 'PostgreSQL'
                cursor.execute('SELECT version();')
                db_version = re.match(r'^PostgreSQL ([\d\.]+) on .+$',
                                      cursor.fetchone()[0]).group(1)
            elif connection.vendor == 'mysql':
                db_engine = 'MySQL'
                cursor.execute('SELECT version();')
                db_version = cursor.fetchone()[0]
            elif connection.vendor == 'sqlite':
                db_engine = 'SQLite'
                db_version = sqlite3.sqlite_version
            else:
                db_engine = connection.vendor
                db_version = ''
        versions['Database'] = ('%s %s' % (db_engine, db_version)).strip()

        return '<dl>%s</dl>' % ''.join(['<dt>%s</dt><dd>%s</dd>' % (k, v)
                                        for k, v in versions.items()])

    def get_graph(self, title, subtitle):
        k = (title, subtitle)
        if k not in self.graphs:
            graph = Graph(title, subtitle)
            self.graphs[k] = graph
        return self.graphs[k]

    def generate(self):
        with open(self.filename, 'w') as f:
            f.write(self.template % {
                'datetime': date_format(now(), 'DATETIME_FORMAT'),
                'conditions': self.conditions,
                'graphs': ''.join([graph.to_html()
                                   for graph in self.graphs.values()]),
            })


class Browser:
    timeout = 20
    selenium_driver = Chrome
    # Installed by chromium-chromedriver under Ubuntu 14.04
    executable_path = '/usr/lib/chromium-browser/chromedriver'
    max_width = 1920
    max_height = 1080

    def __init__(self, id=None, width=None, height=None, x=None, y=None):
        self.id = id
        self.width = width
        self.height = height
        self.x = x
        self.y = y

    def update_window(self):
        if self.width is not None and self.height is not None:
            self.selenium.set_window_size(self.width, self.height)
        if self.x is not None and self.y is not None:
            self.selenium.set_window_position(self.x, self.y)

    def start(self):
        self.selenium = self.selenium_driver(
            executable_path=self.executable_path)
        self.selenium.implicitly_wait(self.timeout)
        self.selenium.set_script_timeout(self.timeout)
        self.selenium.set_page_load_timeout(self.timeout)

        self.update_window()

    def stop(self):
        try:
            self.selenium.quit()
        except (CannotSendRequest, ConnectionError):
            # Occurs when something wrong happens in the middle of a request.
            pass

    def get(self, url):
        return self.selenium.get(url)

    @property
    def current_url(self):
        return self.selenium.current_url

    def reset(self):
        self.selenium.get('about:blank')

    def find(self, css_selector):
        return self.selenium.find_element_by_css_selector(css_selector)

    def find_all(self, css_selector):
        return self.selenium.find_elements_by_css_selector(css_selector)

    def find_link(self, link_text):
        return self.selenium.find_element_by_link_text(link_text)

    def dropdown_choose(self, dropdown_name, value):
        select = Select(self.selenium.find_element_by_name(dropdown_name))
        select.select_by_value(value)

    def type(self, input_name, value):
        self.selenium.find_element_by_name(input_name).send_keys(str(value))

    def submit(self):
        forms = self.selenium.find_elements_by_tag_name('form')
        n_forms = len(forms)
        if n_forms != 1:
            raise NoSuchElementException(
                "Don't know which form to submit, found %d." % len(forms))
        forms[0].submit()

    def find_xpath(self, xpath):
        return self.selenium.find_element_by_xpath(xpath)

    def save_screenshot(self, filename):
        self.selenium.save_screenshot(filename)

    def error_screenshot(self):
        filename = 'error_browser_%d.png' % self.id
        try:
            self.save_screenshot(filename.encode())
            print('Screenshot saved in %s' % filename)
        except NoSuchWindowException:
            pass


class ParallelBrowsers:
    max_width = 1920
    max_height = 1080
    ideal_window_ratio = max_width / max_height

    def __init__(self, amount=0):
        self.browsers = []
        self._amount = 0
        self.amount = amount
        self.tasks = []

    @property
    def amount(self):
        return self._amount

    @amount.setter
    def amount(self, value):
        diff = value - self.amount
        if diff == 0:
            return

        self._amount = value

        if diff > 0:
            while len(self.browsers) < self.amount:
                new_browser = Browser(len(self.browsers))
                self.browsers.append(new_browser)
                new_browser.start()
        elif diff < 0:
            while len(self.browsers) > self.amount:
                self.browsers.pop().stop()

        self.reset()
        self.update_windows()

    def update_windows(self):
        columns, rows = self.find_best_window_grid()
        width = self.max_width // columns
        height = self.max_height // rows

        column = 0
        row = 0
        for i in range(self.amount):
            x = column * width
            y = row * height
            self[i].width = width
            self[i].height = height
            self[i].x = x
            self[i].y = y
            self[i].update_window()
            column += 1
            if column == columns:
                column = 0
                row += 1

    def find_best_window_grid(self):
        if self.amount == 0:
            return 1, 1
        columns = self.amount
        ratios = []
        while columns > 0:
            rows = ceil(self.amount / columns)
            width = self.max_width // columns
            height = self.max_height // rows
            ratio = abs((width / height) - self.ideal_window_ratio)
            ratios.append((ratio, columns, rows))
            columns -= 1
        ratio, columns, rows = min(ratios, key=lambda t: t[0])
        return columns, rows

    def stop(self):
        while self.busy:
            sleep(0.001)

        for browser in self.browsers:
            browser.stop()

    def reset(self):
        for browser in self.browsers:
            browser.reset()

    def error_screenshot(self):
        for browser in self.browsers:
            browser.error_screenshot()

    def garbage_collect_tasks(self):
        for task in self.tasks.copy():
            if not task.is_alive():
                self.tasks.remove(task)
                if task.exception is not None:
                    raise task.exception

        if connection.vendor == 'postgresql':
            # FIXME: This closes idle PostgreSQL connections because we face an
            #        open connection leak. When the leak is fixed, remove this.
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE usename = %s
                        AND state = 'idle'
                        AND query_start < (CURRENT_TIMESTAMP
                                           - INTERVAL '5 seconds');
                """, params=(settings.DATABASES['default']['USER'],))

    @property
    def busy(self):
        return any(t.is_alive() for t in self.tasks)

    def wait_iteration(self):
        self.garbage_collect_tasks()
        sleep(0.001)

    def wait_until_all_available(self):
        while self.busy:
            self.wait_iteration()

    def get_task_for(self, browser):
        for task in self.tasks:
            if task.browser is browser:
                return task

    def get_available_browser(self):
        while True:
            for browser in self.browsers:
                task = self.get_task_for(browser)
                if task is None:
                    return browser
            self.wait_iteration()

    def add_task(self, browser, func):
        task = BrowserTask(browser, func)
        self.tasks.append(task)
        task.start()

    def __getitem__(self, item):
        return self.browsers[item]


class BrowserTask(Thread):
    def __init__(self, browser, func):
        super(BrowserTask, self).__init__()
        self.browser = browser
        self.func = func
        self.exception = None

    def run(self):
        try:
            self.func()
        except Exception as exception:
            self.browser.error_screenshot()
            self.exception = exception


class Server:
    default_port = 8000
    first_port = 1024  # First port available to users.
    procfile_path = 'otree/management/commands/stress_test_procfile'

    def __init__(self, address=None, port=None):
        self.is_external = address is not None

        self.address = 'localhost' if address is None else address

        if port is None:
            port = (self.default_port
                    if self.is_external else self.get_available_port())
        self.port = port

        self.url = 'http://%s:%d' % (self.address, self.port)

        port_available = is_port_available(self.address, self.port)
        if self.is_external:
            if port_available:
                # TODO: Replace this with a ConnectionError
                # when dropping Python 2.
                raise OSError('Cannot connect to %s.' % self.url)
        elif not port_available or port < self.first_port:
            # TODO: Replace this with a ConnectionError when dropping Python 2.
            raise OSError('Port %d is not available to create a server.'
                          % self.port)

    def get_available_port(self):
        port = self.first_port
        while not is_port_available(self.address, port):
            port += 1
        return port

    def start(self):
        if self.is_external:
            return

        print('Starting oTree server on %s...' % self.url)
        command_args = ('honcho', 'start', '-f', self.procfile_path)
        env = os.environ.copy()
        env.update(
            OTREE_PORT=str(self.port),
            USE_BROWSER_BOTS='True',
        )
        self.runserver_process = Popen(
            command_args, stdin=PIPE, stdout=PIPE, stderr=STDOUT, env=env)

        # Waits for the server to be successfully started.
        while is_port_available(self.address, self.port):
            return_code = self.runserver_process.poll()
            if return_code is not None and return_code != 0:
                raise CalledProcessError(
                    return_code, ' '.join(command_args),
                    self.runserver_process.stdout.read())
            sleep(0.1)

    def stop(self):
        if self.is_external:
            return

        print('Stopping oTree server...')
        process = Process(self.runserver_process.pid)
        # We kill each subprocess of the server,
        # the server process will exit once each subprocess exited.
        for subprocess in process.children(recursive=True):
            try:
                subprocess.kill()
            except NoSuchProcess:
                pass
        process.kill()

    def get_url(self, view_name, args=None, kwargs=None):
        return self.url + reverse(view_name, args=args, kwargs=kwargs)


class SkipPage(Exception):
    pass


class Bot:
    def __init__(self, server, browsers, report):
        self.server = server
        self.browsers = browsers
        self.thread_local = local()
        self.browser = None
        self.report = report
        self.graph = None
        self.graph_title = ''
        self.graph_x_title = ''
        self.graph_variable = lambda: 0
        self.session = None

    @property
    def browser(self):
        if self.thread_local.browser is None:
            return self.browsers[0]
        return self.thread_local.browser

    @browser.setter
    def browser(self, browser):
        self.thread_local.browser = browser

    @property
    def session_name(self):
        if self.session is not None:
            return self.session.config['name']
        if hasattr(self, '_session_config'):
            return self._session_config
        raise ValueError('You must fill the attribute `session_config`.')

    @session_name.setter
    def session_name(self, value):
        try:
            config = SESSION_CONFIGS_DICT[value]
        except KeyError:
            raise KeyError('%s is not a valid `session_config`.' % repr(value))
        self._session_config = value
        self.num_participants = config['num_demo_participants']

    def time(self, series_name):
        return self.graph.get_series(
            series_name
        ).time(self.graph_variable(self))

    def get(self, *args, **kwargs):
        return self.browser.get(*args, **kwargs)

    @property
    def current_url(self):
        return self.browser.current_url

    def find(self, *args, **kwargs):
        return self.browser.find(*args, **kwargs)

    def find_all(self, *args, **kwargs):
        return self.browser.find_all(*args, **kwargs)

    def find_link(self, *args, **kwargs):
        return self.browser.find_link(*args, **kwargs)

    def dropdown_choose(self, *args, **kwargs):
        return self.browser.dropdown_choose(*args, **kwargs)

    def type(self, *args, **kwargs):
        return self.browser.type(*args, **kwargs)

    def submit(self, *args, **kwargs):
        return self.browser.submit(*args, **kwargs)

    def skip_page(self):
        raise SkipPage

    def find_xpath(self, *args, **kwargs):
        return self.browser.find_xpath(*args, **kwargs)

    def save_screenshot(self, *args, **kwargs):
        return self.browser.save_screenshot(*args, **kwargs)

    def create_session(self):
        self.session = create_session(self.session_name,
                                      num_participants=self.num_participants)

    def delete_session(self):
        self.session.delete()

    def set_up(self, alter_sessions=True):
        self.graph = self.report.get_graph(self.graph_title, self.session_name)
        self.graph.x_title = self.graph_x_title
        if alter_sessions:
            self.create_session()

    def tear_down(self, alter_sessions=True):
        self.browsers.reset()
        if alter_sessions:
            self.delete_session()

    def get_test_methods(self):
        for attr in dir(self):
            if attr.startswith('test_'):
                method = getattr(self, attr)
                if callable(method):
                    yield attr, method

    def run(self, alter_sessions=True):
        self.set_up(alter_sessions)

        for name, method in self.get_test_methods():
            method()

        self.tear_down(alter_sessions)


class AdminBot(Bot):
    def create_session(self):
        self.get(self.server.get_url('sessions'))
        self.find_link('Create new session').click()
        self.dropdown_choose('session_config', self.session_name)
        self.type('num_participants', self.num_participants)
        form = self.find('#form')
        with self.time('Creation'):
            form.submit()
            # Waits until the page loads.
            self.find_link('Description')
        relative_url = self.current_url[len(self.server.url):]
        self.session = Session.objects.get(
            code=resolve(relative_url).kwargs['code'])

    def delete_session(self):
        self.get(self.server.get_url('sessions'))
        self.find('[name="item-action"][value="%s"]'
                  % self.session.code).click()
        self.find('#action-delete').click()
        confirm = self.find('.modal.in #action-delete-confirm')
        with self.time('Deletion'):
            confirm.click()
            # Waits until the page loads.
            self.find_link('Create new session')

    def test_description_page(self):
        url = self.server.get_url('session_description', (self.session.code,))
        with self.time('Description page'):
            self.get(url)

    def test_links_page(self):
        url = self.server.get_url('session_start_links', (self.session.code,))
        with self.time('Links page'):
            self.get(url)

    def test_monitor_page(self):
        url = self.server.get_url('session_monitor', (self.session.code,))
        with self.time('Monitor page'):
            self.get(url)
            # Waits until the page fully loads.
            self.find_xpath(
                '//td[@data-field = "_id_in_session" and text() = "P%d"]'
                % self.num_participants)

    def test_results_page(self):
        url = self.server.get_url('session_results', (self.session.code,))
        with self.time('Results page'):
            self.get(url)
            # Waits until the page fully loads.
            self.find_xpath(
                '//td[@data-field = "participant_label" and text() = "P%d"]'
                % self.num_participants)

    def test_payments_page(self):
        url = self.server.get_url('session_payments', (self.session.code,))
        with self.time('Payments page'):
            self.get(url)


class PlayerBot(Bot):
    def __init__(self, *args, **kwargs):
        super(PlayerBot, self).__init__(*args, **kwargs)

        self.id_in_session = None
        self.participant = None
        self.player = None
        self.view = None

    @property
    def id_in_session(self):
        return self.thread_local.id_in_session

    @id_in_session.setter
    def id_in_session(self, id_in_session):
        self.thread_local.id_in_session = id_in_session

    @property
    def player(self):
        return self.thread_local.player

    @player.setter
    def player(self, player):
        self.thread_local.player = player

    @property
    def participant(self):
        return self.thread_local.participant

    @participant.setter
    def participant(self, participant):
        self.thread_local.participant = participant

    @property
    def view(self):
        return self.thread_local.view

    @view.setter
    def view(self, view):
        self.thread_local.view = view

    def participate(self, page_number):
        participants = self.session.get_participants()
        self.participant = participants.get(id_in_session=self.id_in_session)
        url = self.server.url + self.participant._start_url()
        if page_number == 1:
            with self.time('Participant page 1'):
                self.get(url)
        else:
            self.get(url)
        # We need to fetch the participant object again since it was modified
        # by the view.
        self.participant = Participant.objects.get(pk=self.participant.pk)
        self.player = self.participant.get_current_player()
        self.view = resolve(self.current_url[len(self.server.url):]).func

    def run_participant(self, browser, id_in_session, page_number, last_page,
                        test_page_method):
        self.browser = browser
        self.id_in_session = id_in_session
        self.participate(page_number)
        try:
            test_page_method()
        except SkipPage:
            return

        is_last_page = page_number == last_page
        page_name = 'finished' if is_last_page else page_number + 1
        with self.time('Participant page %s' % page_name):
            self.submit()

    def run(self, alter_sessions=True):
        self.set_up(alter_sessions)

        test_page_re = re.compile('^test_page_(\d+)$')
        test_page_methods = {}
        for name, method in self.get_test_methods():
            page_match = test_page_re.match(name)
            test_page_methods[int(page_match.group(1))] = method

        # Runs the test_page_1, 2, 3... methods.
        last_page = max(test_page_methods) if test_page_methods else 1
        test_pages = sorted(test_page_methods.items(), key=lambda t: t[0])
        for page_number, test_page_method in test_pages:
            for id_in_session in range(1, self.num_participants + 1):
                browser = self.browsers.get_available_browser()
                self.browsers.add_task(
                    browser,
                    lambda: self.run_participant(
                        browser, id_in_session, page_number, last_page,
                        test_page_method))
            self.browsers.wait_until_all_available()

        self.tear_down(alter_sessions)


class PlayerBotRegistry:
    def __init__(self):
        self.bots = {}

    def add(self, app_name):
        def inner(bot_class):
            if app_name in self.bots:
                raise ValueError("A bot is already registered for '%s'"
                                 % app_name)
            self.bots[app_name] = bot_class
            return bot_class
        return inner

    def get_bots_for(self, session_name):
        session = SESSION_CONFIGS_DICT[session_name]
        return [self.bots[app_name] for app_name in session['app_sequence']
                if app_name in self.bots]

    def __iter__(self):
        for app_name, bot in self.bots.items():
            yield app_name, bot


player_bots = PlayerBotRegistry()


def get_cache_key(participant_code, index, event):
    return 'bots:%s:%s:%s' % (participant_code, index, event)


class NewPlayerBot:
    def __init__(self, server, participant):
        self.server = server
        self.participant = participant
        self.start_url = self.server.url + participant._start_url()
        self.forms_data = OrderedDict()

    @staticmethod
    def start_bots(browser_path, bots):
        args = browser_path.split()[:1]
        for bot in bots:
            args.extend(browser_path.split()[1:])
            args.append(bot.start_url)
        p = Popen(args, stdout=DEVNULL, stderr=DEVNULL, stdin=DEVNULL)
        start = time()
        p.wait(10)
        for bot in bots:
            HUEY.storage.conn.setnx(bot._get_cache_key(0, 'unload'), start)

    @property
    def participant(self):
        return refresh_from_db(self._participant)

    @participant.setter
    def participant(self, value):
        self._participant = value

    @property
    def player(self):
        return self.participant.get_current_player()

    @property
    def view(self):
        return resolve(self.player.url).func

    def __repr__(self):
        return '<PlayerBot %d>' % self.participant.id_in_session

    def _get_cache_key(self, index, event):
        return get_cache_key(self.participant.code, index, event)

    def _get_event_data(self, index, event):
        measured_time = HUEY.storage.conn.get(self._get_cache_key(index,
                                                                  event))
        if measured_time is None:
            return
        return float(measured_time)

    def _get_data(self):
        last_page = self.participant._max_page_index
        for page_index in range(1, last_page+1):
            new_start = self._get_event_data(page_index - 1, 'unload')
            if new_start is not None:
                start = new_start
            end = self._get_event_data(page_index, 'load')
            elapsed_time = (None if start is None or end is None
                            else end - start)
            yield page_index, elapsed_time
        yield 'finished', (self._get_event_data(None, 'finished')
                           - self._get_event_data(last_page, 'unload'))

    def is_waiting(self):
        return self.participant.is_on_wait_page

    def is_finished(self):
        return self._get_event_data(None, 'finished') is not None

    def is_stuck(self):
        return self.is_waiting() or self.is_finished()

    def submit(self, view_func, form_data):
        self.forms_data[view_func] = form_data


class StressTest:
    timeit_iterations = 3
    concurrent_users_steps = 12
    large_sessions_steps = 8

    def __init__(self, sessions_names, browser_path,
                 server_address, server_port):
        if not sessions_names:
            sessions_names = tuple(SESSION_CONFIGS_DICT.keys())
        self.sessions = OrderedDict()
        for session_name in sessions_names:
            try:
                self.sessions[session_name] = \
                    SESSION_CONFIGS_DICT[session_name]
            except KeyError:
                raise KeyError("Undefined session config '%s'." % session_name)

        self.report = Report()

        self.browsers = ParallelBrowsers()
        self.browser_path = browser_path
        self.browser_process = Popen(self.browser_path.split(), stdout=DEVNULL,
                                     stderr=DEVNULL, stdin=DEVNULL)

        self.server = Server(server_address, server_port)
        self.server.start()

        self.bots_per_session = OrderedDict([
            (session_name,
             [bot_class(self.server, self.browsers, self.report)
              for bot_class in player_bots.get_bots_for(session_name)])
            for session_name in self.sessions
        ])
        self.num_participants = lcm([session['num_demo_participants']
                                     for session in self.sessions.values()])

    def test_concurrent_users(self):
        num_participants = (self.num_participants
                            * ceil(self.concurrent_users_steps
                                   / self.num_participants))
        title = ('oTree speed with concurrent users and %d participants'
                 % num_participants)

        steps = list(range(1, self.concurrent_users_steps + 1))
        for session_name in self.sessions:
            progress = tqdm(range(steps[-1]), leave=True,
                            desc='Concurrent users (%s)' % session_name)

            graph = self.report.get_graph(title, session_name)
            graph.x_title = 'Number of concurrent users'

            for concurrent_users in steps:
                session = create_session(
                    session_name, num_participants=num_participants)

                participants = list(session.get_participants())
                while not all(p.is_finished() for p in session.get_participants()):
                    for i in range(0, num_participants, concurrent_users):
                        bots = []
                        for participant in participants[i:i+concurrent_users]:
                            bots.append(NewPlayerBot(self.server, participant))
                        NewPlayerBot.start_bots(
                            self.browser_path, bots[-concurrent_users:])
                        while not all(bot.is_stuck() for bot in bots):
                            sleep(0.001)

                for bot in bots:
                    for page_index, elapsed_time in bot._get_data():
                        series = graph.get_series('Participant page %s'
                                                  % page_index)
                        series.add(concurrent_users, elapsed_time)

                self.report.generate()  # Updates the report on each iteration.
                progress.update()

                session.delete()

    def test_large_sessions(self):
        title = 'oTree speed with large sessions'

        self.browsers.amount = 1

        steps = []
        step = self.num_participants
        while len(steps) < self.large_sessions_steps:
            steps.append(step)
            step *= 2

        for session_name in self.sessions:
            progress = tqdm(range(steps[-1]), leave=True,
                            desc='Large sessions (%s)' % session_name)
            for num_participants in steps:
                admin_bot = AdminBot(self.server, self.browsers, self.report)
                admin_bot.session_name = session_name
                admin_bot.graph_title = '%s (admin)' % title
                admin_bot.graph_x_title = 'Number of participants'
                admin_bot.graph_variable = lambda bot: bot.num_participants
                admin_bot.num_participants = num_participants
                admin_bot.set_up()
                admin_bot.run(alter_sessions=False)

                graph = self.report.get_graph(title, session_name)
                graph.x_title = 'Number of participants'

                bots = []
                for participant in admin_bot.session.get_participants():
                    bots.append(NewPlayerBot(self.server, participant))
                NewPlayerBot.start_bots(self.browser_path, bots)
                while not all(bot.is_finished() for bot in bots):
                    sleep(0.001)

                for bot in bots:
                    for page_index, elapsed_time in bot._get_data():
                        series = graph.get_series('Participant page %s'
                                                  % page_index)
                        series.add(num_participants, elapsed_time)

                admin_bot.tear_down()
                self.report.generate()  # Updates the report on each iteration.
                progress.update(num_participants - progress.n)

    def run(self):
        print('Running all tests %d times...' % self.timeit_iterations)
        try:
            # The timeit iteration is outside and not inside each operation,
            # so we can see approximate results first THEN wait to refine them.
            # This is possible since we measure slow operations. On operations
            # shorter than a millisecond, the timeit loop must be inside.
            for _ in range(self.timeit_iterations):
                self.test_concurrent_users()
                self.test_large_sessions()
        except:
            self.browsers.error_screenshot()
            raise
        finally:
            self.browsers.stop()
            self.browser_process.kill()
            self.server.stop()
            notify('Stress test finished!')


@player_bots.add('tests.simple_game')
class SimpleGamePlayerBot(PlayerBot):
    def test_page_1(self):
        self.type('my_field', 10)

    def test_page_2(self):
        pass


@player_bots.add('tests.multi_player_game')
class MultiPlayerGamePlayerBot(PlayerBot):
    def test_page_1(self):
        if self.player.id_in_group != 1:
            self.skip_page()

    def test_page_2(self):
        self.skip_page()

    def test_page_3(self):
        pass

    def test_page_4(self):
        if self.player.id_in_group != 1:
            self.skip_page()

    def test_page_5(self):
        self.skip_page()

    def test_page_6(self):
        pass


class Command(BaseCommand):
    help = 'Tests oTree performance under a lot of stress.'

    def add_arguments(self, parser):
        parser.add_argument(
            'session_name', type=str, nargs='*',
            help='If omitted, all sessions in SESSION_CONFIGS are run')
        # If you use Firefox, you need to set a setting using 'about:config':
        # 'dom.allow_scripts_to_close_windows' must be true.
        parser.add_argument(
            '-b', '--browser', action='store', type=str, dest='browser_path',
            default='google-chrome',
            help='Path to the browser executable, like "firefox --new-tab"')
        parser.add_argument(
            '--host', action='store', type=str, dest='server_address',
            help='Server domain or IP to be used, '
                 '(if omitted, a server will be started)')
        parser.add_argument(
            '-p', '--port', action='store', type=int, dest='server_port',
            help='Server port')

    def handle(self, *args, **options):
        sessions_names = options['session_name']
        browser_path = options['browser_path']
        server_address = options['server_address']
        server_port = options['server_port']
        StressTest(sessions_names, browser_path,
                   server_address, server_port).run()
