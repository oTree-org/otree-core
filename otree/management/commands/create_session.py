from django.core.management.base import BaseCommand, CommandError, make_option
from otree.session import create_session, get_session_types_dict


class Command(BaseCommand):
    help = "oTree: Create a session."
    args = 'type num_participants'
    option_list = BaseCommand.option_list + (
        make_option(
            "-l", "--label", action="store", type="string", dest="label"
        ),
    )

    def handle(self, *args, **options):
        print 'Creating session...'
        try:
            type, num_participants = args
        except ValueError:
            raise CommandError(
                "Wrong number of arguments (expecting '{}')".format(self.args)
            )
        num_participants = int(num_participants)
        label = options.get('label', '')

        create_session(
            session_type = get_session_types_dict()[type],
            num_participants=num_participants, label=label
        )
