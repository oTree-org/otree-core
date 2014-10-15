import os
from django.core.management.commands import startapp
import otree


class Command(startapp.Command):
    def get_default_template(self):
        return os.path.join(
            os.path.dirname(otree.__file__), 'app_template')

    def handle(self, *args, **options):
        if options.get('template', None) is None:
            options['template'] = self.get_default_template()
        super(Command, self).handle(*args, **options)
