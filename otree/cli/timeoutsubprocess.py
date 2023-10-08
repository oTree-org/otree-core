# run the worker to enforce page timeouts
# even if the user closes their browser
from .base import BaseCommand
from otree.tasks import Worker


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('port', type=int)

    def handle(self, *args, port, **options):
        Worker(port).listen()
