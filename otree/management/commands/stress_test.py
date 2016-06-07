#!/usr/bin/env python

from __future__ import unicode_literals, division, print_function
from collections import OrderedDict, defaultdict
try:
    from http.client import CannotSendRequest
except ImportError:  # Python 2.7
    from httplib import CannotSendRequest
import json
import os
import platform
import re
from socket import socket
from subprocess import call, Popen, PIPE, STDOUT, CalledProcessError
from time import time, sleep
import uuid

from django.core.management.base import BaseCommand
from selenium.common.exceptions import WebDriverException
from selenium.webdriver import Firefox
from selenium.webdriver.support.select import Select


DJANGO_SETTINGS_MODULE = os.environ.get('DJANGO_SETTINGS_MODULE',
                                        'tests.settings')
PROCFILE_PATH = 'otree/management/commands/stress_test_procfile'


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
    except FileNotFoundError:
        pass


class Series:
    def __init__(self, graph, name):
        self.graph = graph
        self.name = name
        self.data = defaultdict(list)
        self.averages = OrderedDict()

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
        self.all_series = []

    def create_series(self, name):
        series = Series(self, name)
        self.all_series.append(series)
        return series

    def to_html(self):
        return self.template % {
            'id': self.id, 'title': json.dumps(self.title),
            'subtitle': json.dumps(self.subtitle),
            'x_title': json.dumps(self.x_title),
            'y_title': json.dumps(self.y_title),
            'y_unit': json.dumps(self.y_unit),
            'x_labels': json.dumps(self.x_labels),
            'all_series': json.dumps([s.to_dict() for s in self.all_series]),
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


class StressTest:
    browser_timeout = 20
    timeit_iterations = 3
    num_participants = OrderedDict((
        ('Simple Game', range(9, 18, 9)),
        ('Multi Player Game', range(9, 18, 9)),
        ('2 Simple Games', range(9, 18, 9)),
    ))

    def __init__(self):
        self.report = Report()
        if self.timeit_iterations < 3:
            raise ValueError('timeit_iterations must be at least 3.')

        print('Starting web browser...')
        self.selenium = Firefox()
        self.selenium.implicitly_wait(self.browser_timeout)
        self.selenium.set_script_timeout(self.browser_timeout)
        self.selenium.set_page_load_timeout(self.browser_timeout)

    def start_server(self):
        print('Starting oTree server...')
        port = 1024  # First port available to users.
        while not is_port_available('localhost', port):
            port += 1
        command_args = ('honcho', 'start', '-f', PROCFILE_PATH)
        env = os.environ.copy()
        env.update(
            DJANGO_SETTINGS_MODULE=DJANGO_SETTINGS_MODULE,
            OTREE_PORT=str(port),
        )
        self.runserver_process = Popen(
            command_args, stdin=PIPE, stdout=PIPE, stderr=STDOUT, env=env)
        self.server_url = 'http://localhost:%d' % port

        # Waits for the server to be successfully started.
        while is_port_available('localhost', port):
            return_code = self.runserver_process.poll()
            if return_code is not None and return_code != 0:
                raise CalledProcessError(
                    return_code, ' '.join(command_args),
                    self.runserver_process.stdout.read())
            sleep(0.1)

    def stop_server(self):
        print('Stopping oTree server...')
        self.runserver_process.terminate()

    def create_session(self, config, num_participants=6):
        self.selenium.get(self.server_url + '/sessions/')
        self.selenium.find_element_by_link_text('Create new session').click()
        select = Select(self.selenium.find_element_by_name('session_config'))
        select.select_by_visible_text(config)
        self.selenium.find_element_by_name('num_participants') \
            .send_keys(str(num_participants))
        form = self.selenium.find_element_by_id('form')
        start = time()
        form.submit()
        # Waits until the page loads.
        self.selenium.find_element_by_link_text('Description')
        creation_time = time() - start
        session_id = re.match(
            r'^%s/SessionStartLinks/(\d+)/$' % re.escape(self.server_url),
            self.selenium.current_url).group(1)
        deletion_time = self.delete_session(session_id)
        return creation_time, deletion_time

    def delete_session(self, session_id):
        self.selenium.get(self.server_url + '/sessions/')
        self.selenium.find_element_by_css_selector(
            '[name="item-action"][value="%s"]' % session_id).click()
        self.selenium.find_element_by_id('action-delete').click()
        confirm = self.selenium.find_element_by_id('action-delete-confirm')
        start = time()
        confirm.click()
        # Waits until the page loads.
        self.selenium.find_element_by_link_text('Create new session')
        return time() - start

    def test_large_sessions(self, config):
        print('Testing large sessions (%s)...' % config)
        graph = self.report.create_graph(
            'oTree performance when creating large sessions', '(%s)' % config)
        creation_series = graph.create_series('Creation')
        deletion_series = graph.create_series('Deletion')
        for num_participants in self.num_participants[config]:
            print('Testing with %d participants...' % num_participants)
            for _ in range(self.timeit_iterations):
                creation_time, deletion_time = self.create_session(
                    config, num_participants=num_participants)
                creation_series.add(num_participants, creation_time)
                deletion_series.add(num_participants, deletion_time)
            self.report.generate()

    def run(self):
        try:
            self.start_server()
            for config in self.num_participants:
                self.test_large_sessions(config)
        except WebDriverException:
            self.selenium.save_screenshot('selenium_error.png')
            raise
        except KeyboardInterrupt:
            pass
        finally:
            self.report.generate()
            try:
                self.selenium.quit()
            except CannotSendRequest:  # Occurs when quitting selenium
                # in the middle of a request.
                pass
            self.stop_server()
            notify('Stress test finished!')


class Command(BaseCommand):
    help = 'Tests oTree performance under a lot of stress.'

    def handle(self, *args, **options):
        StressTest().run()
