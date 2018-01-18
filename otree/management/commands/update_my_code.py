from django.core.management.base import BaseCommand


class Command(BaseCommand):

    def handle(self, **options):
        print('Before using this command, you need to upgrade otree-core.')