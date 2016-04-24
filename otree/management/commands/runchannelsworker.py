from channels.management.commands.runworker import Command as RunworkerCommand
from channels.management.commands.runserver import WorkerThread
from django.core.management import BaseCommand, CommandError
from channels import channel_layers, DEFAULT_CHANNEL_LAYER
from channels.log import setup_logger
import time


class Command(RunworkerCommand):

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--num-threads', action='store', dest='num_threads', default=4,
            type=int,
            help='Number of worker threads')


    def handle(self, *args, **options):
        # Get the backend to use
        self.verbosity = options.get("verbosity", 1)

        self.logger = setup_logger('django.channels', self.verbosity)
        self.channel_layer = channel_layers[options.get("layer", DEFAULT_CHANNEL_LAYER)]
        # Check that handler isn't inmemory
        if self.channel_layer.local_only():
            raise CommandError(
                "You cannot span multiple processes with the in-memory layer. " +
                "Change your settings to use a cross-process channel layer."
            )
        # Check a handler is registered for http reqs
        self.channel_layer.router.check_default()
        # Launch a worker
        self.logger.info("Running worker against channel layer %s", self.channel_layer)
        # Run the worker
        worker_threads = []
        num_threads = options['num_threads']
        for _ in range(num_threads):
            worker = WorkerThread(self.channel_layer, self.logger)
            worker.daemon = True
            worker.start()
            worker_threads.append(worker)
        while True:
            time.sleep(5)
