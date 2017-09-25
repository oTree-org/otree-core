import logging
from django.core.management.base import BaseCommand
import otree.bots.browser
from otree.common_internal import get_redis_conn
from otree.session import create_session


# =============================================================================
# LOGGING
# =============================================================================

logger = logging.getLogger('otree.botworker')


# =============================================================================
# COMMAND
# =============================================================================

class Command(BaseCommand):
    help = "oTree: Run the worker for browser bots."

    def handle(self, *args, **options):
        redis_conn = get_redis_conn()
        otree.bots.browser.redis_flush_bots(redis_conn)
        worker = otree.bots.browser.Worker(redis_conn)
        session = create_session('misc_3p', num_participants=30)
        #participant_codes = session.participant_set.values_list('code', flat=True)
        worker.initialize_session(session_pk=session.pk)
        #for code in participant_codes:
        #    worker.initialize_session(code)
