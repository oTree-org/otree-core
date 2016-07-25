import logging
from django.core.management.base import BaseCommand
from otree.bots.browser import Worker, redis_flush_bots
from otree.common_internal import get_redis_conn


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
        redis_flush_bots(redis_conn)
        consumer = Worker(redis_conn)
        consumer.loop()
