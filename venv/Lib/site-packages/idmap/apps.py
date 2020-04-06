from django.apps import AppConfig


class IdMapConfig(AppConfig):
    name = 'idmap'
    verbose_name = 'Django identity mapper'

    def ready(self):

        from . import signals