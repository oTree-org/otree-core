from django.core.management.base import BaseCommand, CommandError, make_option
from ptree.session import create_session

class Command(BaseCommand):
    help = "pTree: Create a session."
    args = 'type [amount]'
    option_list = BaseCommand.option_list + (
        make_option("-l", "--label", action="store", type="string", dest="label"),
    )

    def handle(self, *args, **options):
        print 'Creating sessions...'
        if len(args) not in {1, 2}:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        type = args[0]

        if len(args) == 2:
            amount = int(args[1])
        else:
            amount = 1

        label = options.get('label', '')

        for i in range(amount):
            create_session(type=type, label=label)