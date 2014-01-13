# -*- coding: utf-8 -*-

# documentation build configuration file, created by sphinx-quickstart

import sys
import os

sys.path.insert(0, os.path.abspath('..'))
sys.path.insert(0, os.path.abspath('../..'))

import django.conf
if not django.conf.settings.configured:
    django.conf.settings.configure(default_settings=django.conf.global_settings)

extensions = [
    'sphinx.ext.autodoc',
]

templates_path = []

source_suffix = '.rst'

master_doc = 'field_descriptions'

project = u' '
copyright = u' '

version = '1'
release = '1'