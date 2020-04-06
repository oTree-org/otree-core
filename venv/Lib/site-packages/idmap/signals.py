"""
Signals are used to automatically flush the idmap cache on finish request,
migrate / syncdb and instance deletion, and to make sure to catch cascades
"""

from django.dispatch import Signal, receiver
from django.core.signals import request_finished
from django.db.models.signals import pre_delete, post_migrate


pre_flush = Signal(providing_args=['using'])
post_flush = Signal(providing_args=['using'])


@receiver((post_migrate, request_finished))
def flush_idmap(using=None, **kwargs):
    """
    Flushes the idmap cache on migrate and on request end
    """
    from .functions import flush
    flush(db=using)


@receiver(pre_delete)
def flush_cached_instance(sender, instance, **kwargs):
    """
    Flushes a deleted instance from the idmap cache
    """
    from .models import IdMapModel
    if issubclass(sender, IdMapModel):
        sender.flush_cached_instance(instance)
