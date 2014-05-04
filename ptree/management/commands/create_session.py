from django.core.management.base import BaseCommand, CommandError, make_option
from ptree.session import create_session

class Command(BaseCommand):
    help = "pTree: Create a session."
    args = 'type [label]'
    option_list = BaseCommand.option_list + (
        make_option("-l", "--label", action="store", type="string", dest="label"),
    )

    def handle(self, *args, **options):
        print 'Creating session...'
        if len(args) != 1:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        type = args[0]

        label = options.get('label', '')
        create_session(type=type, label=label)