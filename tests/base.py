import warnings

import splinter.browser
from django.conf import settings
import django.test

# =============================================================================
# HELPER
# =============================================================================


# 2016-06-16: is this still needed? TODO
class OTreeTestClient(django.test.client.Client):

    def login(self):
        return super(OTreeTestClient, self).login(
            username=settings.ADMIN_USERNAME, password=settings.ADMIN_PASSWORD)


class TestCase(django.test.TestCase):

    client_class = OTreeTestClient

    def assertWarns(self, warning, callable, *args, **kwds):
        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter('always')

            callable(*args, **kwds)

        condition = any(item.category == warning for item in warning_list)
        msg = "'{}' not warned".format(str(warning))
        self.assertTrue(condition, msg)


class OTreePhantomBrowser(splinter.browser.PhantomJSWebDriver):

    # splinter.Browser is actually a function, not a class
    def __init__(self, live_server_url):
        self.live_server_url = live_server_url
        super().__init__()

            #user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'
        #)

    def go(self, relative_url):
        self.visit(self.live_server_url + relative_url)