import asyncio
import logging
import time
from starlette.middleware.sessions import SessionMiddleware  # noqa
from starlette.middleware.base import BaseHTTPMiddleware
from otree.common import _SECRET, lock

from otree.database import db, NEW_IDMAP_EACH_REQUEST

logger = logging.getLogger('otree.perf')


lock2 = asyncio.Lock()


class CommitTransactionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        async with lock2:
            if NEW_IDMAP_EACH_REQUEST:
                db.new_session()
            response = await call_next(request)
            if response.status_code < 500:
                db.commit()
            else:
                # it's necessary to roll back. if i don't, the values get saved to DB
                # (even though i don't commit, not sure...)
                db.rollback()
            return response


class PerfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()

        response = await call_next(request)

        # heroku has 'X-Request-ID'
        request_id = request.headers.get('X-Request-ID')
        if request_id:
            # only log this info on Heroku
            elapsed = time.time() - start
            msec = int(elapsed * 1000)
            logger.info(f'own_time={msec}ms request_id={request_id}')

        return response
