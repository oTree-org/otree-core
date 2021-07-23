from argparse import ArgumentParser
from importlib import import_module
import sys


class BaseCommand:
    def outer_handle(self, args):
        parser = self._create_parser()
        options = parser.parse_args(args)
        return self.handle(**vars(options))

    def handle(self, *args, **options):
        raise NotImplementedError

    def _create_parser(self):
        parser = ArgumentParser()
        self.add_arguments(parser)
        return parser

    def add_arguments(self, parser):
        """
        Entry point for subclassed cli to add custom arguments.
        """
        pass


def call_command(cmd, *args):
    try:
        module = import_module(f'otree.cli.{cmd}')
    except ModuleNotFoundError:
        sys.exit(f"No command named '{cmd}'")
    module.Command().outer_handle(args)
