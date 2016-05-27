# deprecation shim
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def run_from_argv(self, argv):
        print(
            'celery command no longer exists in oTree 0.5. '
            'You should update your Procfile.'
        )