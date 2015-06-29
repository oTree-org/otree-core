import sys

from django.core.management.base import BaseCommand
import honcho.manager


class Command(BaseCommand):
    help = 'Run otree development server.'

    processes = ({
        'name': 'web',
        'command': 'python manage.py runserver',
    }, {
        'name': 'worker',
        'command': (
            'python manage.py celery worker '
                '--app=otree.celery.app:app '
                '--loglevel=INFO'
        ),
    })

    def handle(self, *args, **options):
        manager = honcho.manager.Manager()
        for process in self.processes:
            manager.add_process(process['name'], process['command'])

        manager.loop()
        sys.exit(manager.returncode)
