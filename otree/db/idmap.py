from __future__ import absolute_import
from contextlib import contextmanager
from idmap.metaclass import SharedMemoryModelBase  # noqa
import idmap.models
import idmap.tls
import threading


_toggle = threading.local()


def flush_cache():
    # The cache was not initialized yet, so we don't need to clear it yet.
    if not hasattr(idmap.tls._tls, 'idmap_cache'):
        return
    for key in list(idmap.tls._tls.idmap_cache.keys()):
        del idmap.tls._tls.idmap_cache[key]


def is_active():
    return getattr(_toggle, 'is_active', False)


def deactivate_cache():
    _toggle.is_active = False


def activate_cache():
    flush_cache()
    _toggle.is_active = True


@contextmanager
def use_cache():
    activate_cache()
    yield
    deactivate_cache()


class SharedMemoryModel(idmap.models.SharedMemoryModel):
    class Meta:
        abstract = True

    # The ``get_cached_instance`` method is the canonical access point for
    # idmap to retrieve objects for a particular model from the cache. If it
    # returns None, then it's meant as a cache miss and the object is retrieved
    # from the database.

    # We intercept this so that we can disable the idmap cache. That is
    # required as we only want it to be active on experiment views. idmap has
    # it's problems when used together with django-channels as channels is
    # re-using threads between requests. That will result in a shared idmap
    # cache between requests, which again results in unpredictable data
    # returned from the cache as it might contain stale data.

    # The solution is to only use the cache when processing a view and clear
    # the cache before activating the use. See the activate_cache() for the
    # implementation.
    @classmethod
    def get_cached_instance(cls, pk):
        if is_active():
            return idmap.tls.get_cached_instance(cls, pk)
        else:
            return None
