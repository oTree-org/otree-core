import contextlib
import logging

from sqlalchemy import MetaData

from .base import BaseCommand
from otree.database import engine, AnyModel
from sqlalchemy.orm import close_all_sessions

logger = logging.getLogger('otree')

MSG_RESETDB_SUCCESS_FOR_HUB = 'Created new tables and columns.'
MSG_DB_ENGINE_FOR_HUB = 'Database engine'

print_function = print


class Command(BaseCommand):
    help = (
        "Resets your development database to a fresh state. "
        "All data will be deleted."
    )

    def add_arguments(self, parser):
        ahelp = (
            'Tells the resetdb command to NOT prompt the user for ' 'input of any kind.'
        )
        parser.add_argument(
            '--noinput',
            action='store_false',
            dest='interactive',
            default=True,
            help=ahelp,
        )

    def _confirm(self) -> bool:
        print_function("This will delete and recreate your database. ")
        answer = input("Proceed? (y or n): ")
        if answer:
            return answer[0].lower() == 'y'
        return False

    def handle(self, *, interactive, **options):
        if interactive and not self._confirm():
            print_function('Canceled.')
            return

        # hub depends on this string
        logger.info(f"{MSG_DB_ENGINE_FOR_HUB}: {engine.name}")

        with contextlib.closing(engine.connect()) as bind:
            trans = bind.begin()
            old_meta = MetaData()

            # these will hang if any other processes have a long-running DB connection
            old_meta.reflect(bind)
            old_meta.drop_all(bind)

            # tables get automatically created during init_orm()
            # but since we just deleted tables, we need to re-create
            AnyModel.metadata.create_all(bind)
            trans.commit()
        # oTree Hub depends on this string
        logger.info(MSG_RESETDB_SUCCESS_FOR_HUB)
