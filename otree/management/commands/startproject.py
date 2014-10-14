import os
from django.core.management.commands import startproject
import otree


class Command(startproject.Command):
    def get_default_template(self):
        return os.path.join(
            os.path.dirname(otree.__file__), 'project_template')

    def handle(self, *args, **options):
        if options.get('template', None) is None:
            options['template'] = self.get_default_template()
        super(Command, self).handle(*args, **options)

    def validate_name(self, name, app_or_project):
        super(Command, self).validate_name(name, app_or_project)
        if name.lower() == "otree":
            raise startproject.CommandError(
                "%r is not allowed as project name." % name)
