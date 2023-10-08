from time import sleep
from .base import BaseCommand


class Command(BaseCommand):
    '''legacy: doesn't do anything since we moved timeoutworker into main dyno'''

    def handle(self, *args, **options):
        while True:
            sleep(10)
