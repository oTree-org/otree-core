#!/usr/bin/env python

from __future__ import unicode_literals, division, print_function
from collections import OrderedDict
import json
import platform
import re
from socket import socket
from subprocess import call, Popen, PIPE, STDOUT, CalledProcessError
from time import time, sleep
import uuid

from psutil import Process, virtual_memory
from selenium.common.exceptions import WebDriverException
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
    except FileNotFoundError:
        pass


REPORT_TEMPLATE = """
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


class Series:
    def __init__(self, name):
        self.name = name
        self.data = []

    def to_dict(self):
        return {'name': self.name, 'data': self.data}


class Graph:
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

    def to_html(self):
        kwargs = {
            'id': self.id, 'title': json.dumps(self.title),
            'subtitle': json.dumps(self.subtitle),
            'x_title': json.dumps(self.x_title),
            'y_title': json.dumps(self.y_title),
            'y_unit': json.dumps(self.y_unit),
            'x_labels': json.dumps(self.x_labels),
            'all_series': json.dumps([s.to_dict() for s in self.all_series]),
        }
        return """
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
        """ % kwargs


class StressTest:
    browser_timeout = 20
    timeit_iterations = 3
    num_participants = OrderedDict((
        ('Simple Game', range(9, 189, 9)),
        ('Multi Player Game', range(9, 189, 9)),
        ('2 Simple Games', range(9, 189, 9)),
    ))

    def __init__(self):
        self.graphs = []

        print('Starting web browser...')
        self.selenium = Firefox()
        self.selenium.implicitly_wait(self.browser_timeout)
        self.selenium.set_script_timeout(self.browser_timeout)
        self.selenium.set_page_load_timeout(self.browser_timeout)

    def get_conditions(self):
        versions = OrderedDict()
        with open('/proc/cpuinfo') as f:
            versions['CPU'] = re.search(r'^model name\s+: (.+)$', f.read(),
                                        flags=re.MULTILINE).group(1)
        GiB = 1 << 30
        versions.update((
            ('RAM', '%.2f GiB' % (virtual_memory().total / GiB)),
            ('Linux distribution', ' '.join(
                platform.linux_distribution()).strip()),
            ('Python', platform.python_version()),
        ))
        return '<dl>%s</dl>' % ''.join([
            '<dt>%s</dt><dd>%s</dd>' % (k, v) for k, v in versions.items()])

    def start_server(self):
        print('Starting oTree server...')
        port = 1024  # First port available to users.
        while not is_port_available('localhost', port):
            port += 1
        command_args = ('./manage.py', 'runserver', str(port))
        self.runserver_process = Popen(command_args,
                                       stdout=PIPE, stderr=STDOUT)
        self.server_url = 'http://localhost:%d' % port

        while is_port_available('localhost', port):
            return_code = self.runserver_process.poll()
            if return_code is not None and return_code != 0:
                raise CalledProcessError(
                    return_code, ' '.join(command_args),
                    self.runserver_process.stdout.read())
            sleep(0.1)

    def stop_server(self):
        print('Stopping oTree server...')
        process = Process(self.runserver_process.pid)
        # We send ctrl+c to each subprocess of the server, the server process
        # will exit once each child exited.
        for child in process.children():
            child.kill()
        self.runserver_process.wait()

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
        graph = Graph('oTree performance when creating large sessions',
                      '(%s)' % config)
        self.graphs.append(graph)
        creation_series = Series('Creation')
        deletion_series = Series('Deletion')
        graph.all_series.append(creation_series)
        graph.all_series.append(deletion_series)
        for num_participants in self.num_participants[config]:
            print('Testing with %d participants...' % num_participants)
            creation_times = []
            deletion_times = []
            for _ in range(self.timeit_iterations):
                creation_time, deletion_time = self.create_session(
                    config, num_participants=num_participants)
                creation_times.append(creation_time)
                deletion_times.append(deletion_time)
            graph.x_labels.append(num_participants)
            creation_series.data.append(
                sum(creation_times) / self.timeit_iterations)
            deletion_series.data.append(
                sum(deletion_times) / self.timeit_iterations)

    def run(self):
        try:
            self.start_server()
            for config in self.num_participants:
                self.test_large_sessions(config)
        except WebDriverException:
            self.selenium.save_screenshot('selenium_error.png')
            raise
        finally:
            with open('stress_test_report.html', 'w') as f:
                f.write(REPORT_TEMPLATE % {
                    'conditions': self.get_conditions(),
                    'graphs': ''.join([graph.to_html()
                                       for graph in self.graphs]),
                })
            print('Report generated in stress_test_report.html')
            self.stop_server()
            self.selenium.quit()
            notify('Stress test finished!')

if __name__ == '__main__':
    StressTest().run()
