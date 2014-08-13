#!/usr/bin/env python
import os, sys
import django.conf
import {{ project_name }}.settings

if __name__ == "__main__":
    if not django.conf.settings.configured:
        django.conf.settings.configure(**{{ project_name }}.settings.settings)
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)