import django.test
import idmap.tls


class IDMapTestCaseMixin(object):
    def _post_teardown(self):
        super(IDMapTestCaseMixin, self)._post_teardown()
        # We need to reset the cache for the idmap as all the tests run in the
        # same thread and therefore share a cache. The models get flushed after
        # every test run, but this won't send a signal. That's why the idmap
        # cache doesn't know about the change in the DB.
        idmap.tls.init_idmap()


class TestCase(IDMapTestCaseMixin, django.test.TestCase):
    pass
