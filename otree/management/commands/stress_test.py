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
import os
import platform
import re
from socket import socket
from subprocess import call, Popen, PIPE, STDOUT, CalledProcessError
from time import time, sleep
import uuid

from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse, resolve
from django.utils.formats import date_format
from django.utils.timezone import now
from selenium.common.exceptions import (
    NoSuchElementException, WebDriverException,
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

    def __init__(self, title, subtitle='', x_title='Number of participants',
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
        self.graphs = []
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

    def create_graph(self, title, subtitle):
        graph = Graph(title, subtitle)
        self.graphs.append(graph)
        return graph

    def generate(self):
        with open(self.filename, 'w') as f:
            f.write(self.template % {
                'datetime': date_format(now(), 'DATETIME_FORMAT'),
                'conditions': self.conditions,
                'graphs': ''.join([graph.to_html()
                                   for graph in self.graphs]),
            })


class Browser:
    timeout = 20
    selenium_driver = Chrome
    # Installed by chromium-chromedriver under Ubuntu 14.04
    executable_path = '/usr/lib/chromium-browser/chromedriver'

    def start(self):
        print('Starting web browser...')
        self.selenium = self.selenium_driver(
            executable_path=self.executable_path)
        self.selenium.implicitly_wait(self.timeout)
        self.selenium.set_script_timeout(self.timeout)
        self.selenium.set_page_load_timeout(self.timeout)

    def stop(self):
        print('Stopping web browser...')
        try:
            self.selenium.quit()
        except (CannotSendRequest, ConnectionResetError):
            pass  # Occurs when something wrong happens
                  # in the middle of a request.

    def get(self, url):
        return self.selenium.get(url)

    @property
    def current_url(self):
        return self.selenium.current_url

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
        self.runserver_process.terminate()
        self.runserver_process.wait(3)

    def get_url(self, view_name, args=None, kwargs=None):
        return self.url + reverse(view_name, args=args, kwargs=kwargs)


class SkipPage(Exception):
    pass


class Bot:
    session_config = None
    num_participants = 1

    def __init__(self, server, browser, report):
        self.server = server
        self.browser = browser
        if self.session_config is None:
            raise ValueError(
                'You must fill the class attribute `session_config`.')
        self.graph = report.create_graph('', self.session_config)
        self.session = None
        self.id_in_session = None
        self.participant = None
        self.player = None

    def time(self, series_name):
        return self.graph.get_series(series_name).time(self.num_participants)

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
        self.create_session()

    def tear_down(self):
        self.delete_session()

    def run(self, graph_title=''):
        self.graph.title = graph_title
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
        last_page = max(test_page_methods)
        test_pages = sorted(test_page_methods.items(), key=lambda t: t[0])
        for i, test_page in test_pages:
            for id_in_session in range(1, self.num_participants + 1):
                self.id_in_session = id_in_session
                self.participate()
                try:
                    test_page()
                except SkipPage:
                    continue

                is_last_page = i == last_page
                page_name = 'finished' if is_last_page else i + 1
                with self.time('Participant page %s' % page_name):
                    self.submit()

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

    def participate(self):
        self.get(self.server.get_url('session_start_links',
                                     (self.session.pk,)))
        link = self.find_all(
            'a[href*="/InitializeParticipant/"]')[self.id_in_session - 1]
        url = link.get_attribute('href')
        with self.time('Participant page 1'):
            self.get(url)

        relative_url = url[len(self.server.url):] + '/'
        self.participant = Participant.objects.get(
            code=resolve(relative_url).kwargs['participant_code'])
        self.player = self.participant.get_current_player()


class BotRegistry(list):
    def add(self, bot_class):
        self.append(bot_class)
        return bot_class


bot_registry = BotRegistry()


class StressTest:
    timeit_iterations = 3
    large_sessions_steps = 8

    def __init__(self):
        self.report = Report()

        self.browser = Browser()
        self.browser.start()

        self.server = Server()
        self.server.start()

        self.bots = [bot_class(self.server, self.browser, self.report)
                     for bot_class in bot_registry]
        self.num_participants = lcm([bot.num_participants
                                     for bot in self.bots])

    def test_large_sessions(self):
        title = 'oTree speed when creating large sessions'

        steps = []
        step = self.num_participants
        while len(steps) < self.large_sessions_steps:
            steps.append(step)
            step *= 2

        for bot in self.bots:
            progress = tqdm(range(steps[-1]), leave=True,
                            desc='Large sessions (%s)' % bot.session_config)
            for num_participants in steps:
                bot.num_participants = num_participants
                bot.run(graph_title=title)
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
                self.test_large_sessions()
        except WebDriverException:
            self.browser.save_screenshot('selenium_error.png')
            raise
        except BadStatusLine:
            pass  # Occurs when the browser is closed prematurely.
        finally:
            self.browser.stop()
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
