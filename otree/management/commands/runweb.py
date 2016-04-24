import os
from django.core.management.base import BaseCommand

CMD = 'daphne otree.asgi:channel_layer --port $PORT --bind 0.0.0.0 -v2'

class Command(BaseCommand):

    def handle(self, *args, **options):
        os.system(CMD)