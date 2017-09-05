from unittest import mock
from six import StringIO
from otree.management.commands.webandworkers import OTreeHonchoManager
from django.core.management import call_command
from otree.management import cli
from tests import TestCase


class OTreeAndDjangoVersion(TestCase):

    @mock.patch("otree.get_version", return_value="foo")
    @mock.patch("django.get_version", return_value="faa")
    def test_otree_and_django_version(self, dget_version, oget_version):
        actual = cli.otree_and_django_version()
        expected = 'oTree: foo - Django: faa'

        self.assertTrue(dget_version.called)
        self.assertTrue(oget_version.called)
        self.assertEqual(actual, expected)


class OTreeManagementUtility(TestCase):

    @mock.patch("sys.argv", new=["otree", "--help"])
    @mock.patch("platform.system", return_value="No-Windows")
    def test_help(self, *args):
        arguments = ["otree", "--help"]

        expected = StringIO()
        with mock.patch("sys.stdout", new=expected):
            cli.execute_from_command_line(arguments, "otree")

        utility = cli.OTreeManagementUtility(arguments)
        actual = StringIO()
        with mock.patch("sys.stdout", new=actual):
            utility.execute()

        self.assertEquals(actual.getvalue(), expected.getvalue())

    def test_commands_only(self, *args):
        utility = cli.OTreeManagementUtility([])
        main_help_text = utility.main_help_text().splitlines()
        for command in utility.main_help_text(commands_only=True).splitlines():
            prefix = "  {} - ".format(command)
            found = False
            for line in main_help_text:
                if line.startswith(prefix):
                    found = True
                    break
            if not found:
                self.fail("Command '{}' no found in help".format(command))

    def test_settings_exception(self):
        expected = ('Note that only Django core commands are listed as '
                    'settings are not properly configured (error: foo).')

        utility = cli.OTreeManagementUtility([])
        utility.settings_exception = "foo"
        main_help_text = utility.main_help_text().splitlines()

        self.assertEquals(main_help_text[-1], expected)

        utility = cli.OTreeManagementUtility([])
        utility.settings_exception = None
        main_help_text = utility.main_help_text().splitlines()

        self.assertNotEquals(main_help_text[-1], expected)


class ExecuteFromCommandLine(TestCase):

    @mock.patch("platform.system", return_value="No-Windows")
    @mock.patch("otree.management.cli.OTreeManagementUtility")
    def test_execute_from_command_line_runserver(self, *args):
        management, system = args
        cli.execute_from_command_line(["otree", "runserver"], "script.py")
        management.assert_called_with(["otree", "runserver"])

    # not working at the moment because of SSL server
    '''
    @mock.patch("platform.system", return_value="No-Windows")
    @mock.patch("otree.management.cli.OTreeManagementUtility")
    @mock.patch("django.conf.LazySettings.AWS_ACCESS_KEY_ID", create=True)
    def test_execute_from_command_line_runserver_ssh(self, *args):
        key, management, system = args
        cli.execute_from_command_line(["otree", "runserver"], "script.py")
        management.assert_called_with(["otree", "runsslserver"])
    '''

    # not working at the moment because of pypi cli check
    '''
    @mock.patch("platform.system", return_value="No-Windows")
    @mock.patch("sys.stdout")
    @mock.patch("otree.management.cli.otree_and_django_version",
                return_value="foo")
    def test_execute_from_command_line_runserver_no_env_command(self, *args):
        version, stdout, system = args
        cli.execute_from_command_line(["version"], "script.py")
        self.assertTrue(version.called)
        stdout.write.assert_called_with("foo\n")
    '''

from collections import namedtuple
CommandAndResult = namedtuple(
    'CommandAddrPort', field_names=['command', 'address', 'port'])


class OTreeCli(TestCase):

    @mock.patch("sys.argv", new=["--help"])
    @mock.patch("otree.management.cli.execute_from_command_line")
    def test_clean_run(self, execute_from_command_line):
        cli.otree_cli()
        execute_from_command_line.assert_called_with(["--help"], 'otree')

    @mock.patch("sys.argv", new=["--version"])
    @mock.patch("otree.management.cli.execute_from_command_line")
    @mock.patch("os.getcwd", return_value="foo")
    def test_add_pwd(self, *args):
        gcwd, execute_from_command_line = args
        with mock.patch("sys.path", new=[]) as path:
            cli.otree_cli()
            self.assertEquals(path, ["foo"])
        self.assertTrue(gcwd.called)
        execute_from_command_line.assert_called_with(["--version"], 'otree')

    # 2017-06-17:
    # what's the point of patching execute_from_command_line and calling otree_cli?
    # why not just use call_command? That seems better because it covers calls
    # using 'otree' script and 'python manage.py', and just tests the command itself,
    # not that argv is passed correctly, which Django handles for us
    # also it's more standard

    @mock.patch("sys.exit")
    @mock.patch.dict('os.environ', {'PORT': '5000'})
    @mock.patch.object(OTreeHonchoManager, 'loop')
    @mock.patch.object(OTreeHonchoManager, 'add_otree_process')
    def test_webandworkers(self, add_otree_process, *args):
        specs = [
            # should respect the $PORT env var, for Heroku
            ('webandworkers', '0.0.0.0', '5000'),
            # new syntax, to be consistent with runserver
            ('runprodserver 127.0.0.1:80', '127.0.0.1', '80'),
            ('runprodserver 8002', '0.0.0.0', '8002'),
            # legacy syntax
            ('runprodserver --port=81', '0.0.0.0', '81')
        ]

        for command, expected_address, expected_port in specs:
            add_otree_process.reset_mock()
            call_command(*command.split(' '))
            add_otree_process.assert_any_call(
                'daphne',
                'daphne otree.asgi:channel_layer -b {} -p {}'.format(
                    expected_address, expected_port))

    @mock.patch("sys.exit")
    @mock.patch.object(OTreeHonchoManager, 'loop')
    @mock.patch.object(OTreeHonchoManager, 'add_otree_process')
    def test_runprodserver(self, add_otree_process, *args):
        call_command('runprodserver')
        add_otree_process.assert_any_call(
            'botworker', 'otree botworker')
        add_otree_process.assert_any_call(
            'timeoutworkeronly',
            'otree timeoutworkeronly',
        )
