#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import otree

procfile_path = os.path.join(
    os.path.dirname(otree.__file__), 'project_template', 'Procfile')

with open(procfile_path, 'r') as procfile:
    procfile_contents = procfile.read()

DEPRECATION_STRING = '''
oTree is using a new server. You should start it with a different command.
You should change your Procfile to the below:

{}
'''.format(procfile_contents)

print(DEPRECATION_STRING)

def application(environ, start_response):
    data = DEPRECATION_STRING.encode('utf-8')
    start_response("200 OK", [
        ("Content-Type", "text/plain"),
        ("Content-Length", str(len(data)))
    ])
    return iter([data])