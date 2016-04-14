from django.core.management.base import CommandError
from djcelery.management.commands.celery import Command as CeleryCommand


class Command(CeleryCommand):
    def run_from_argv(self, argv):
        if len(argv) > 2:
            raise CommandError('runceleryworker does not take arguments')
        # Emulate the command:
        # otree celery worker --app=otree.celery.app:app --loglevel=INFO
        argv = argv + [
            'worker',
            '--app=otree.celery.app:app',
            '--loglevel=INFO'
        ]
        return super(Command, self).run_from_argv(argv)
