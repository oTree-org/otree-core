#!/usr/bin/env python

from __future__ import unicode_literals, division, print_function
from collections import OrderedDict, defaultdict
from fractions import gcd
from functools import reduce
from django.conf import settings
from django.db import connection
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
from subprocess import call, Popen, PIPE, STDOUT, CalledProcessError
from threading import Thread, local
from time import time, sleep
import uuid

from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse, resolve
from django.utils.formats import date_format
from django.utils.timezone import now
from psutil import Process, NoSuchProcess
from selenium.common.exceptions import (
    NoSuchElementException, NoSuchWindowException
)
from selenium.webdriver import Chrome
from selenium.webdriver.support.select import Select
from tqdm import tqdm

from otree.models import Session, Participant


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
                    x: -20 // compensates the legend width.
                },
                subtitle: {
                    text: %(subtitle)s,
                    x: -20 // compensates the legend width.
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
        self.graphs = {}
        self.filename = 'stress_test_report.html'
        print('The report will be generated in %s' % self.filename)

        self.conditions = self.get_conditions()

    def get_conditions(self):
        versions = OrderedDict()
        # TODO: This works only on Linux.
        with open('/proc/cpuinfo') as f:
            versions['CPU'] = re.search(r'^model name\s+: (.+)$', f.read(),
                                        flags=re.MULTILINE).group(1)
        # TODO: This works only on Linux.
        with open('/proc/meminfo') as f:
            ram = re.search(r'^MemTotal:\s+(\d+) kB$', f.read(),
                            flags=re.MULTILINE).group(1)
            ram = int(ram) * 1024  # Since meminfo in fact uses kiB, not kB.
            GiB = 1 << 30
            versions['RAM'] = '%.2f GiB' % (ram / GiB)
        versions.update((
            # TODO: This works only on Linux.
            ('Linux distribution', ' '.join(
                platform.linux_distribution()).strip()),
            ('Python', platform.python_version()),
        ))
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

    def start(self):
        self.selenium = self.selenium_driver(
            executable_path=self.executable_path)
        self.selenium.implicitly_wait(self.timeout)
        self.selenium.set_script_timeout(self.timeout)
        self.selenium.set_page_load_timeout(self.timeout)

        if self.width is not None and self.height is not None:
            self.selenium.set_window_size(self.width, self.height)
        if self.x is not None and self.y is not None:
            self.selenium.set_window_position(self.x, self.y)

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
        select.select_by_visible_text(value)

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


class ParallelBrowsers:
    max_width = 1920
    max_height = 1080
    ideal_window_ratio = max_width / max_height

    def __init__(self, amount=1):
        self.amount = amount

        columns, rows = self.find_best_window_grid()
        width = self.max_width // columns
        height = self.max_height // rows

        column = 0
        row = 0
        self.browsers = []
        for i in range(amount):
            x = column * width
            y = row * height
            self.browsers.append(Browser(i, width, height, x, y))
            column += 1
            if column == columns:
                column = 0
                row += 1

        self.tasks = []

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

    def start(self):
        for browser in self.browsers:
            browser.start()

    def stop(self):
        while self.busy:
            sleep(0.001)

        for browser in self.browsers:
            browser.stop()

    def reset(self):
        for browser in self.browsers:
            browser.reset()

    def garbage_collect_tasks(self):
        for task in self.tasks.copy():
            if not task.is_alive():
                self.tasks.remove(task)
                if task.exception is not None:
                    raise task.exception

        # FIXME: This closes idle PostgreSQL connections because we face an
        #        open connection leak. When the leak is fixed, remove this.
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE usename = %s AND state = 'idle';
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
            filename = 'error.png'
            try:
                self.browser.save_screenshot(filename.encode())
                print('Screenshot saved in %s' % filename)
            except NoSuchWindowException:
                pass
            self.exception = exception


class Server:
    procfile_path = 'otree/management/commands/stress_test_procfile'

    def start(self):
        print('Starting oTree server...')
        port = 1024  # First port available to users.
        while not is_port_available('localhost', port):
            port += 1
        command_args = ('honcho', 'start', '-f', self.procfile_path)
        env = os.environ.copy()
        env['OTREE_PORT'] = str(port)
        self.runserver_process = Popen(
            command_args, stdin=PIPE, stdout=PIPE, stderr=STDOUT, env=env)
        self.url = 'http://localhost:%d' % port

        # Waits for the server to be successfully started.
        while is_port_available('localhost', port):
            return_code = self.runserver_process.poll()
            if return_code is not None and return_code != 0:
                raise CalledProcessError(
                    return_code, ' '.join(command_args),
                    self.runserver_process.stdout.read())
            sleep(0.1)

    def stop(self):
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
    session_config = None
    num_participants = 1

    def __init__(self, server, browsers, report):
        self.server = server
        self.browsers = browsers
        self.thread_local = local()
        self.browser = None
        if self.session_config is None:
            raise ValueError(
                'You must fill the class attribute `session_config`.')
        self.report = report
        self.graph = None
        self.graph_title = ''
        self.graph_x_title = ''
        self.graph_variable = lambda: 0
        self.session = None
        self.id_in_session = None
        self.participant = None
        self.player = None

    @property
    def browser(self):
        if self.thread_local.browser is None:
            return self.browsers[0]
        return self.thread_local.browser

    @browser.setter
    def browser(self, browser):
        self.thread_local.browser = browser

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
        self.get(self.server.get_url('sessions'))
        self.find_link('Create new session').click()
        self.dropdown_choose('session_config', self.session_config)
        self.type('num_participants', self.num_participants)
        form = self.find('#form')
        with self.time('Creation'):
            form.submit()
            # Waits until the page loads.
            self.find_link('Description')
        relative_url = self.current_url[len(self.server.url):]
        self.session = Session.objects.get(
            pk=resolve(relative_url).kwargs['pk'])

    def delete_session(self):
        self.get(self.server.get_url('sessions'))
        self.find('[name="item-action"][value="%s"]'
                  % self.session.pk).click()
        self.find('#action-delete').click()
        confirm = self.find('.modal.in #action-delete-confirm')
        with self.time('Deletion'):
            confirm.click()
            # Waits until the page loads.
            self.find_link('Create new session')

    def set_up(self):
        self.graph = self.report.get_graph(self.graph_title,
                                           self.session_config)
        self.graph.x_title = self.graph_x_title
        self.create_session()

    def tear_down(self):
        self.browsers.reset()
        self.delete_session()

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

    def run(self):
        self.set_up()

        test_page_re = re.compile('^test_page_(\d+)$')
        test_page_methods = {}
        for attr in dir(self):
            if attr.startswith('test_'):
                method = getattr(self, attr)
                if callable(method):
                    page_match = test_page_re.match(attr)
                    if page_match is None:
                        method()
                    else:
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

        self.tear_down()

    def test_description_page(self):
        url = self.server.get_url('session_description', (self.session.pk,))
        with self.time('Description page'):
            self.get(url)

    def test_links_page(self):
        url = self.server.get_url('session_start_links', (self.session.pk,))
        with self.time('Links page'):
            self.get(url)

    def test_monitor_page(self):
        url = self.server.get_url('session_monitor', (self.session.pk,))
        with self.time('Monitor page'):
            self.get(url)
            # Waits until the page fully loads.
            self.find_xpath(
                '//td[@data-field = "_id_in_session" and text() = "P%d"]'
                % self.num_participants)

    def test_results_page(self):
        url = self.server.get_url('session_results', (self.session.pk,))
        with self.time('Results page'):
            self.get(url)
            # Waits until the page fully loads.
            self.find_xpath(
                '//td[@data-field = "participant_label" and text() = "P%d"]'
                % self.num_participants)

    def test_payments_page(self):
        url = self.server.get_url('session_payments', (self.session.pk,))
        with self.time('Payments page'):
            self.get(url)


class BotRegistry(list):
    def add(self, bot_class):
        self.append(bot_class)
        return bot_class


bot_registry = BotRegistry()


class StressTest:
    timeit_iterations = 3
    concurrent_users_steps = 16
    large_sessions_steps = 8
    large_sessions_concurrent_users = 2

    def __init__(self):
        self.report = Report()

        self.browsers = ParallelBrowsers(0)

        self.server = Server()
        self.server.start()

        self.bots = [bot_class(self.server, self.browsers, self.report)
                     for bot_class in bot_registry]
        self.num_participants = lcm([bot.num_participants
                                     for bot in self.bots])

    def test_concurrent_users(self):
        num_participants = (self.num_participants
                            * ceil(self.concurrent_users_steps
                                   / self.num_participants))
        title = ('oTree speed with concurrent users and %d participants'
                 % num_participants)

        steps = list(range(1, self.concurrent_users_steps + 1))
        progress = tqdm(range(steps[-1]), leave=True,
                        desc='Concurrent users')
        for concurrent_users in steps:
            self.browsers = ParallelBrowsers(concurrent_users)
            self.browsers.start()
            for bot in self.bots:
                bot.browsers = self.browsers
                bot.graph_title = title
                bot.graph_x_title = 'Number of concurrent users'
                bot.graph_variable = lambda bot: bot.browsers.amount
                bot.num_participants = num_participants
                bot.run()
                self.report.generate()  # Updates the report on each iteration.
            self.browsers.stop()
            progress.update()

    def test_large_sessions(self):
        title = ('oTree speed with large sessions and %d concurrent users'
                 % self.large_sessions_concurrent_users)

        self.browsers = ParallelBrowsers(self.large_sessions_concurrent_users)
        self.browsers.start()

        steps = []
        step = self.num_participants
        while len(steps) < self.large_sessions_steps:
            steps.append(step)
            step *= 2

        for bot in self.bots:
            bot.browsers = self.browsers
            bot.graph_title = title
            bot.graph_variable = lambda bot: bot.num_participants
            bot.graph_x_title = 'Number of participants'
            progress = tqdm(range(steps[-1]), leave=True,
                            desc='Large sessions (%s)' % bot.session_config)
            for num_participants in steps:
                bot.num_participants = num_participants
                bot.run()
                self.report.generate()  # Updates the report on each iteration.
                progress.update(num_participants - progress.n)

        self.browsers.stop()

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
        except BadStatusLine:
            pass  # Occurs when the browser is closed prematurely.
        finally:
            self.browsers.stop()
            self.server.stop()
            notify('Stress test finished!')


@bot_registry.add
class SimpleGameBot(Bot):
    session_config = 'Simple Game'

    def test_page_1(self):
        self.type('my_field', 10)

    def test_page_2(self):
        pass


@bot_registry.add
class MultiPlayerGameBot(Bot):
    session_config = 'Multi Player Game'
    num_participants = 3

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


@bot_registry.add
class TwoSimpleGamesBot(Bot):
    session_config = '2 Simple Games'

    # FIXME: This application is broken, write the page tests when it is fixed.


class Command(BaseCommand):
    help = 'Tests oTree performance under a lot of stress.'

    def handle(self, *args, **options):
        StressTest().run()
