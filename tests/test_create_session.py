import uuid

from django.core.management import call_command

from otree.models import Session

from .utils import TestCase
from .simple import models as sg_models
from .saving import models as sgc_models
import six
from six.moves import range
from otree.session import create_session, SESSION_CONFIGS_DICT
from django.core.urlresolvers import reverse
import splinter
from channels.tests import ChannelTestCase, HttpClient
from otree.channels import consumers


class TestCreateSessionsCommand(TestCase):

    def test_create_two_sessions_output(self):
        num_sessions = 2
        for i in range(num_sessions):
            call_command('create_session', 'simple', "1")
        created_sessions = Session.objects.count()
        self.assertEqual(created_sessions, num_sessions)

    def test_create_one_session(self):
        call_command('create_session', 'simple', "1")
        self.assertEqual(Session.objects.count(), 1)
        session = Session.objects.get()
        self.assertEqual(session.config['name'], 'simple')

        self.assertEqual(sg_models.Subsession.objects.count(), 1)
        subsession = sg_models.Subsession.objects.get()

        self.assertEqual(sg_models.Player.objects.count(), 1)

        player = sg_models.Player.objects.get()
        self.assertEqual(player.session, session)
        self.assertEqual(player.subsession, subsession)

    def test_session_vars(self):
        key = six.text_type(uuid.uuid4())
        value = six.text_type(uuid.uuid4())

        call_command('create_session', 'two_simple_games', "1")

        self.assertEqual(Session.objects.count(), 1)
        session = Session.objects.get()
        self.assertEqual(session.config['name'], 'two_simple_games')

        self.assertEqual(sg_models.Subsession.objects.count(), 1)
        self.assertEqual(sgc_models.Subsession.objects.count(), 1)
        subsession0 = sg_models.Subsession.objects.get()
        subsession1 = sgc_models.Subsession.objects.get()

        self.assertEqual(sg_models.Player.objects.count(), 1)
        self.assertEqual(sgc_models.Player.objects.count(), 1)

        # retrieve player of first subsession
        player0 = sg_models.Player.objects.get()

        # add a random key value
        player0.participant.vars[key] = value
        player0.participant.save()

        # retrieve player of second subsession
        player1 = sgc_models.Player.objects.get()

        # validate all
        self.assertTrue(player0.session == player1.session == session)
        self.assertEqual(player0.subsession, subsession0)
        self.assertEqual(player1.subsession, subsession1)

        # test the random key value in second subsession
        self.assertEqual(player1.participant.vars.get(key), value)

    def test_edit_session_config(self):
        session_config_name = 'simple'
        config_key = 'use_browser_bots'
        session_config = SESSION_CONFIGS_DICT[session_config_name]
        original_config_value = session_config[config_key]
        new_config_value = not original_config_value

        session = create_session(
            'simple', num_participants=1,
            edited_session_config_fields={config_key: new_config_value})
        self.assertEqual(session.config[config_key], new_config_value)

        # make sure it didn't affect the value for future sessions
        # (this bug occurred because we mutated the dictionary)
        session2 = create_session(
            'simple', num_participants=1)
        self.assertEqual(session2.config[config_key], original_config_value)


class ViewTests(ChannelTestCase):

    def test_create_session(self):
        br = splinter.Browser('django')

        config_name = 'edit_session_config'

        new_values = {
            'int': 1,
            'float': 1.57,
            'bool': True,
            'str': 'hello2',
            'participation_fee': 1
        }

        create_session_url = reverse('CreateSession')
        br.visit(create_session_url)

        form_values = {
            'session_config': 'edit_session_config',
            'num_participants': '1',
        }

        for k, v in new_values.items():
            if isinstance(v, bool):
                br.check('{}.{}'.format(config_name, k))
            else:
                field_name = '{}.{}'.format(config_name, k)
                form_values[field_name] = str(v)

        br.fill_form(form_values)
        button = br.find_by_value('Create')
        button.click()

        # make sure undesired fields are not present? Like you can't edit
        # 'app_sequence' or 'num_demo_participants'.
        # test fail to create session

        # i can't test waiting for the session
        # because i don't know the pre_create_id

        message = self.get_next_message('otree.create_session', require=True)
        consumers.create_session(message)

        # test connecting before session is created

        session = Session.objects.first()
        config = session.config

        ORIGINAL_CONFIG = SESSION_CONFIGS_DICT[config_name]
        for k, v in new_values.items():
            # make sure we actually changed it, and that we didn't mutate
            # the original config
            self.assertNotEqual(config[k], ORIGINAL_CONFIG[k])
            # make sure equal to new value
            self.assertEqual(config[k], v)

'''
Don't have a test case for WaitForSession consumer because it's routinely
tested manually, and writing the test is a lot of work to test a small amount
of code.
'''

'''
Not working because splinter doesn't seem to recognize formaction, so I get:
Method Not Allowed (POST): /sessions/

Anyway, this test doesn't seem very useful. The test is longer than the code itself.

ToggleArchived will have the same issue

class DeleteTests(TestCase):
    def test_delete(self):

        session = create_session('simple', num_participants=1)
        br = splinter.Browser('django')
        sessions_url = reverse('Sessions')
        br.visit(sessions_url)
        # it seems splinter Django browser doesn't let you select checkboxes by value?
        # so i can't specify the session code
        #checkboxes = br.find_by_name('session')
        #for checkbox in checkboxes:
        #    print('checking checkbox')
        #    checkbox.check()
        br.check('session')
        br.find_by_id('action-delete-confirm').click()
        self.assertFalse(Session.objects.filter(code=session.code).exists())
'''