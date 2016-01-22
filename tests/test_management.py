#!/usr/bin/env python
# -*- coding: utf-8 -*-

import mock

from six import StringIO

from django.core.management.base import CommandError

from otree.management import cli
from .base import TestCase


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

    @mock.patch("platform.system", return_value="Windows")
    @mock.patch("sys.exit")
    @mock.patch("subprocess.Popen")
    @mock.patch("subprocess.Popen.wait")
    @mock.patch("os.path.exists", return_value=False)
    def test_execute_from_command_line_windows_fails(self, *args):
        exists, wait, Popen, sexit, system = args
        with self.assertRaises(CommandError):
            cli.execute_from_command_line(["foo", "runserver"], "script")
        self.assertTrue(exists.called)
        self.assertFalse(wait.called)
        self.assertFalse(Popen.called)
        self.assertFalse(sexit.called)
        self.assertTrue(system.called)

    @mock.patch("platform.system", return_value="Windows")
    @mock.patch("sys.exit")
    @mock.patch("subprocess.Popen")
    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("sys.stdin")
    @mock.patch("sys.stderr")
    @mock.patch("sys.stdout")
    @mock.patch("otree.management.cli.OTreeManagementUtility")
    def test_execute_from_command_line_windows(self, *args):
        management, stdout, stderr, stdin, exists, Popen, sexit, system = args
        cli.execute_from_command_line(["foo", "runserver"], "script")
        self.assertEquals(
            Popen.call_args[1:][0],
            {"stdin": stdin, "stdout": stdout, "stderr": stderr})
        self.assertTrue(sexit.called)
        self.assertTrue(system.called)
        self.assertTrue(exists.called)
        self.assertTrue(exists.called)
        self.assertTrue(management.called)

    @mock.patch("platform.system", return_value="No-Windows")
    @mock.patch("otree.management.cli.OTreeManagementUtility")
    def test_execute_from_command_line_runserver(self, *args):
        management, system = args
        cli.execute_from_command_line(["foo", "runserver"], "script.py")
        management.assert_called_with(["foo", "runserver"])

    @mock.patch("platform.system", return_value="No-Windows")
    @mock.patch("otree.management.cli.OTreeManagementUtility")
    @mock.patch("django.conf.LazySettings.AWS_ACCESS_KEY_ID", create=True)
    def test_execute_from_command_line_runserver_ssh(self, *args):
        key, management, system = args
        cli.execute_from_command_line(["foo", "runserver"], "script.py")
        management.assert_called_with(["foo", "runsslserver"])

    @mock.patch("platform.system", return_value="No-Windows")
    @mock.patch("sys.stdout")
    @mock.patch("otree.management.cli.otree_and_django_version",
                return_value="foo")
    def test_execute_from_command_line_runserver_no_env_command(self, *args):
        version, stdout, system = args
        cli.execute_from_command_line(["version"], "script.py")
        self.assertTrue(version.called)
        stdout.write.assert_called_with("foo\n")


class OTreeCli(TestCase):

    @mock.patch("sys.stdout")
    @mock.patch("sys.stderr")
    @mock.patch("sys.argv", new=["otree", "runserver"])
    def test_import_settings_fail(self, *args):
        settings_patch = mock.patch(
            "otree.management.cli.settings",
            create=True)
        with settings_patch as settings:
            type(settings).INSTALLED_APPS = mock.PropertyMock(
                side_effect=ImportError)
            with self.assertRaises(SystemExit):
                cli.otree_cli()

    @mock.patch("sys.argv", new=["--help"])
    @mock.patch("otree.management.cli.execute_from_command_line")
    def test_clean_run(self, execute_from_command_line):
        cli.otree_cli()
        execute_from_command_line.assert_called_with(["--help"], "otree")

    @mock.patch("sys.argv", new=["--version"])
    @mock.patch("otree.management.cli.execute_from_command_line")
    @mock.patch("os.getcwd", return_value="foo")
    def test_add_pwd(self, *args):
        gcwd, execute_from_command_line = args
        with mock.patch("sys.path", new=[]) as path:
            cli.otree_cli()
            self.assertEquals(path, ["foo"])
        self.assertTrue(gcwd.called)
        execute_from_command_line.assert_called_with(["--version"], "otree")


class OTreeHerokuCli(TestCase):

    @mock.patch("sys.stdout")
    @mock.patch("sys.stderr")
    def test_import_settings_fail(self, *args):
        with mock.patch("django.conf.settings", create=True) as settings:
            type(settings).INSTALLED_APPS = mock.PropertyMock(
                side_effect=ImportError)
            with self.assertRaises(SystemExit):
                cli.otree_heroku_cli()

    @mock.patch("sys.argv", new=["--version"])
    @mock.patch("otree.management.deploy.heroku.execute_from_command_line")
    def test_clean_run(self, execute_from_command_line):
        cli.otree_heroku_cli()
        execute_from_command_line.assert_called_with(["--version"])

    @mock.patch("sys.argv", new=["--version"])
    @mock.patch("otree.management.deploy.heroku.execute_from_command_line")
    @mock.patch("os.getcwd", return_value="foo")
    def test_add_pwd(self, *args):
        gcwd, execute_from_command_line = args
        with mock.patch("sys.path", new=[]) as path:
            cli.otree_heroku_cli()
            self.assertEquals(path, ["foo"])
        self.assertTrue(gcwd.called)
        execute_from_command_line.assert_called_with(["--version"])
