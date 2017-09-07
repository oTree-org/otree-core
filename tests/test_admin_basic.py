import importlib
import sys

import django.test.client
import splinter
import splinter.browser
from django.conf import settings
from django.core.urlresolvers import reverse

from .utils import OTreePhantomBrowser, TestCase, get_path


def reload_urlconf():
    if settings.ROOT_URLCONF in sys.modules:
        module = sys.modules[settings.ROOT_URLCONF]
    else:
        module = importlib.import_module(settings.ROOT_URLCONF)
    importlib.reload(module)


class TestAdminBasic(TestCase):

    def setUp(self):
        self.browser = django.test.client.Client()

    def test_admin_basic(self):
        for tab in [
            'demo',
            'sessions',
            'rooms',
            'create_session',
            'server_check',
            'accounts/login'
        ]:
            response = self.browser.get('/{}/'.format(tab), follow=True)
            self.assertEqual(response.status_code, 200)

    def test_login(self):
        login_url = '/accounts/login/'
        resp = self.browser.post(
            login_url,
            data={
                'username': settings.ADMIN_USERNAME,
                'password': settings.ADMIN_PASSWORD,
            },
            follow=True
        )

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(login_url, get_path(resp, if_no_redirect=login_url))

    def test_auth_level(self):

        # whether you should be granted access when not logged in,
        # based on AUTH_LEVEL
        auth_level_outcomes = {
            'STUDY': {
                'OutOfRangeNotification': True,
                'DemoIndex': False,
                'ExportIndex': False,
            },
            'DEMO': {
                'OutOfRangeNotification': True,
                'DemoIndex': True,
                'ExportIndex': False,
            },
            '': {
                'OutOfRangeNotification': True,
                'DemoIndex': True,
                'ExportIndex': True,
            }
        }

        for AUTH_LEVEL in auth_level_outcomes:
            with self.settings(AUTH_LEVEL=AUTH_LEVEL):
                reload_urlconf()
                for url_name in auth_level_outcomes[AUTH_LEVEL]:
                    url = reverse(url_name)
                    resp = self.browser.get(url, follow=True)
                    is_login_page = any(
                        ['accounts/login' in ele[0]
                         for ele in resp.redirect_chain])
                    access_granted = not is_login_page
                    self.assertEqual(
                        access_granted,
                        auth_level_outcomes[AUTH_LEVEL][url_name],
                        msg='AUTH_LEVEL={}, url_name={}, access_granted={}'.format(
                            AUTH_LEVEL, url_name, access_granted
                        )
                    )
            # reload URLconf to restore back to its original state,
            # so other tests can run normally
            reload_urlconf()

'''
# We can't enable these test cases until we upgrade to CHannels 1.0+
class TestAdminJS(ChannelLiveServerTestCase):

    def setUp(self):
        self.browser = splinter.Browser('phantomjs')

    def test_create_session(self):
        br = self.browser
        create_session_url = '{}{}'.format(self.live_server_url, reverse('CreateSession'))
        br.visit(create_session_url)
        br.fill_form({
            'session_config': 'simple',
            'num_participants': '1',
        })
        button = br.find_by_value('Create')
        button.click()
        self.assertTrue(br.is_text_present('Simple Game: session', wait_time=3))


class TestRoomJS(ChannelLiveServerTestCase):

    def test_presence(self):
        # admin browser
        abr = OTreePhantomBrowser(live_server_url=self.live_server_url)

        # participant browser
        pbr = OTreePhantomBrowser(live_server_url=self.live_server_url)

        room_name = 'with_labels'

        # participant opens waiting page
        room_url = reverse('AssignVisitorToRoom', args=[room_name])
        pbr.go(room_url)

        pbr.fill('participant_label', 'JohnSmith')
        button = pbr.find_by_tag('button')
        button.click()
        waiting_url = pbr.url

        # admin opens RoomWithoutSession
        abr.go(reverse('RoomWithoutSession', args=[room_name]))

        # within a few seconds, he should see that participant online,
        # but not another participant.
        self.assertTrue(
            abr.is_element_present_by_css(
                '#present-participant-label-JohnSmith.count-this', wait_time=5))
        self.assertFalse(
            abr.is_element_present_by_css(
                '#present-participant-label-Bob.count-this'))

        # if participant closes the browser, he should go offline
        # go to some other URL
        pbr.go('/')

        self.assertFalse(
            abr.is_element_present_by_css(
                '#present-participant-label-JohnSmith.count-this', wait_time=1))

        # comes back online
        # need to use visit, not go, because it's an absolute URL
        pbr.visit(waiting_url)

        # admin creates a session in the room
        abr.fill_form({
            'session_config': 'simple',
            'num_participants': '1',
        })
        button = abr.find_by_value('Create')
        button.click()

        # within a few seconds, the participant should be redirected
        my_field_present = pbr.is_element_present_by_name('my_field', wait_time=2)
        self.assertTrue(my_field_present)
'''