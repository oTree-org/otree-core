from otree.session import create_session
from otree.bots.bot import ParticipantBot
from .utils import TestCase, run_bots, ConnectingWSClient
from unittest import mock
import tests.wait_page.views
import splinter
import tests.waitpage_template.models
from channels.tests import ChannelTestCase
import tests.wait_page.views
import tests.waitpage_skip_race.views

class TestWaitForAllGroups(TestCase):
    def setUp(self):
        session = create_session(
            'wait_page', num_participants=4, use_cli_bots=True)
        subsession = session.get_subsessions()[0]
        self.group1 = subsession.get_groups()[0]

    def start_some_players(self, should_be_stuck):
        bots = []
        for player in self.group1.get_players():
            bot = ParticipantBot(player.participant, load_player_bots=False)
            bots.append(bot)
        for bot in bots:
            bot.open_start_url()
        for bot in bots:
            bot.open_start_url()
            self.assertEqual(bot.on_wait_page(), should_be_stuck)

    def test_dont_wait_for_all(self):
        self.start_some_players(should_be_stuck=False)

    def test_wait_for_all_groups(self):
        with mock.patch.object(
                tests.wait_page.views.MyWait,
                'wait_for_all_groups',
                new_callable=mock.PropertyMock,
                return_value=True):
            self.start_some_players(should_be_stuck=True)


class TestSkipWaitPage(TestCase):
    def setUp(self):
        session = create_session(
            'skip_wait_page', num_participants=2, use_cli_bots=True)
        bots = []
        for participant in session.get_participants():
            bot = ParticipantBot(participant, load_player_bots=False)
            bots.append(bot)
        self.bots = bots

    def visit(self, ordered_bots):
        for bot in ordered_bots:
            bot.open_start_url()
        for bot in ordered_bots:
            bot.open_start_url()
            self.assertFalse(bot.on_wait_page())

    def test_skipper_visits_last(self):
        self.visit(self.bots)

    def test_waiter_visits_last(self):
        self.visit(reversed(self.bots))


class TestWaitPageMisuse(TestCase):

    def test_attribute_access(self):
        '''Test accessing self.player, self.group, self.participant in a wait page'''
        run_bots('waitpage_misuse', num_participants=2)


class TemplateTests(TestCase):
    def test_customization(self):

        # need 2 participants so the wait page is not skipped
        session = create_session('waitpage_template', num_participants=2)
        participant = session.participant_set.first()
        br = splinter.Browser('django')
        Constants = tests.waitpage_template.models.Constants
        with self.assertTemplateUsed(template_name=Constants.wait_page_template):
            br.visit(participant._start_url())
        for substring in [
            Constants.custom_title_text,
            Constants.custom_body_text,
        ]:
            self.assertTrue(br.is_text_present(substring))


class Wrapper:
    '''Wrapper for base class so that test runner doesn't run this'''

    class RaceTestsBase(ChannelTestCase):

        '''Race conditions in connecting to wait pages'''

        config_name = None
        wait_page_index = None
        WaitPageClass = None # type: otree.views.abstract.WaitPage

        def play(self, participant):
            self.br.visit(participant._start_url())

        def get_ws_client(self):
            page = self.WaitPageClass()
            self.p1.refresh_from_db()
            page.set_attributes(participant=self.p1)
            return ConnectingWSClient(path=page.socket_url())

        def setUp(self):
            session = create_session(self.config_name, num_participants=2)
            self.p1, self.p2 = session.get_participants()

            #path = channel_utils.wait_page_path(
            #    session.pk, group_id_in_subsession=1, index_in_pages=self.wait_page_index)
            #self.p1_client = ConnectingWSClient(path=path)
            self.br = splinter.Browser('django')

        def test_slow_websocket(self):
            p1 = self.p1
            p2 = self.p2
            #p1_client = self.p1_client

            self.play(p1)
            self.play(p2)

            p1_client = self.get_ws_client()
            p1_client.connect()
            self.assertEqual(
                p1_client.receive(),
                {'status': 'ready'}
            )

        def test_other_player_last(self):
            p1 = self.p1
            p2 = self.p2

            self.play(p1)
            p1_client = self.get_ws_client()
            p1_client.connect()

            self.play(p2)
            self.assertEqual(
                p1_client.receive(),
                {'status': 'ready'}
            )


class RaceTests(Wrapper.RaceTestsBase):
    config_name = 'wait_page'
    WaitPageClass = tests.wait_page.views.MyWait


class SkipRaceTests(Wrapper.RaceTestsBase):

    '''Need a separate test for wait pages that are skipped, because
    they go through a different code path (_increment_index_in_pages)
    '''

    config_name = 'waitpage_skip_race'
    WaitPageClass = tests.waitpage_skip_race.views.MyWait

    def play(self, participant):
        self.br.visit(participant._start_url())
        self.br.find_by_tag('button').first.click()