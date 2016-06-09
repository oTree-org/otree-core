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
from django.core.urlresolvers import reverse
from selenium.common.exceptions import (
    NoSuchElementException, WebDriverException,
)
from selenium.webdriver import Firefox
from selenium.webdriver.support.select import Select


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
        if x not in self.graph.x_labels:
            self.graph.x_labels.append(x)
        self.set_average(x)

    def set_average(self, x):
        l = self.data[x].copy()
        if len(l) > 2:
            # We make an average without the extreme values.
            l.remove(min(l))
            l.remove(max(l))
            self.averages[x] = sum(l) / len(l)

    def to_dict(self):
        return {'name': self.name,
                'data': list(self.averages.values())}


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
                    categories: %(x_labels)s
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
        self.x_labels = []
        self.all_series = {}

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
            'x_labels': json.dumps(self.x_labels),
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
                'conditions': self.conditions,
                'graphs': ''.join([graph.to_html()
                                   for graph in self.graphs]),
            })


class Browser:
    timeout = 20
    selenium_driver = Firefox

    def start(self):
        print('Starting web browser...')
        self.selenium = self.selenium_driver()
        self.selenium.implicitly_wait(self.timeout)
        self.selenium.set_script_timeout(self.timeout)
        self.selenium.set_page_load_timeout(self.timeout)

    def stop(self):
        print('Stopping web browser...')
        try:
            self.selenium.quit()
        except CannotSendRequest:
            pass  # Occurs when something wrong happens
            # in the middle of a request.

    def get(self, *args, **kwargs):
        return self.selenium.get(*args, **kwargs)

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
                "Don't know which form to submit, found %d" % forms)
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
        self.runserver_process.wait()

    def get_url(self, view_name, args=None, kwargs=None):
        return self.url + reverse(view_name, args=args, kwargs=kwargs)


class Bot:
    name = 'oTree performance when creating large sessions'
    session_config = None
    num_participants = 1

    def __init__(self, server, browser, report):
        self.server = server
        self.browser = browser
        if self.session_config is None:
            raise ValueError(
                'You must fill the class attribute `session_config`.')
        self.graph = report.create_graph(self.name, self.session_config)

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
        self.session_id = re.match(
            r'^%s/SessionStartLinks/(\d+)/$' % re.escape(self.server.url),
            self.current_url).group(1)

    def delete_session(self):
        self.get(self.server.get_url('sessions'))
        self.find(
            '[name="item-action"][value="%s"]' % self.session_id).click()
        self.find('#action-delete').click()
        confirm = self.find('#action-delete-confirm')
        with self.time('Deletion'):
            confirm.click()
            # Waits until the page loads.
            self.find_link('Create new session')

    def set_up(self):
        self.create_session()

    def tear_down(self):
        self.delete_session()

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
        last_page = max(test_page_methods)
        test_pages = sorted(test_page_methods.items(), key=lambda t: t[0])
        for i, test_page in test_pages:
            for participant_number in range(1, self.num_participants + 1):
                self.participate(participant_number)
                test_page()

                is_last_page = i == last_page
                page_name = 'finished' if is_last_page else i + 1
                with self.time('Participant page %s' % page_name):
                    self.submit()
                    # Waits until the page fully loads.
                    if is_last_page \
                            or participant_number == self.num_participants:
                        # The next page only appears if we are
                        # at the last page or the last to submit the form,
                        # otherwise it is the wait page below.
                        self.find('input[name="csrfmiddlewaretoken"]')
                    else:
                        self.find_xpath('//h3[@class = "panel-title" '
                                        'and text() = "Please wait"]')

        self.tear_down()

    def test_results_page(self):
        link = self.find_link('Results')
        with self.time('Results page'):
            link.click()
            # Waits until the page fully loads.
            self.find_xpath(
                '//td[@data-field = "participant_label" and text() = "P%d"]'
                % self.num_participants)

    def participate(self, participant_number=1):
        self.get(self.server.get_url('session_start_links',
                                     (self.session_id,)))
        link = self.find_all(
            'a[href*="/InitializeParticipant/"]')[participant_number - 1]
        url = link.get_attribute('href')
        with self.time('Participant page 1'):
            self.get(url)
            # Waits until the page fully loads.
            self.find('input[name="csrfmiddlewaretoken"]')


class BotRegistry(list):
    def add(self, bot_class):
        self.append(bot_class)
        return bot_class


bot_registry = BotRegistry()


class StressTest:
    timeit_iterations = 3
    steps = 20
    min_step_size = 10

    def __init__(self):
        self.report = Report()
        if self.timeit_iterations < 3:
            raise ValueError('timeit_iterations must be at least 3.')

        self.browser = Browser()
        self.browser.start()

        self.server = Server()
        self.server.start()

        self.bots = [bot_class(self.server, self.browser, self.report)
                     for bot_class in bot_registry]
        start = lcm([bot.num_participants for bot in self.bots])
        step = start
        while step < self.min_step_size:
            step += start
        self.steps_iterator = range(step, step * (self.steps + 1), step)

    def run(self):
        try:
            for bot in self.bots:
                print('Testing large sessions (%s)...' % bot.session_config)
                for num_participants in self.steps_iterator:
                    print('Testing with %d participants...' % num_participants,
                          end='\r')
                    bot.num_participants = num_participants
                    for _ in range(self.timeit_iterations):
                        bot.run()
                        # Updates the report on each iteration.
                        self.report.generate()
                print()  # Leaves the last printed line of the iteration.
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
        pass

    def test_page_2(self):
        pass


@bot_registry.add
class TwoSimpleGamesBot(Bot):
    session_config = '2 Simple Games'


class Command(BaseCommand):
    help = 'Tests oTree performance under a lot of stress.'

    def handle(self, *args, **options):
        StressTest().run()
