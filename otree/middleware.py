from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
import time
from starlette.requests import Request
import logging
from otree.database import db, NEW_IDMAP_EACH_REQUEST
from otree.common import _SECRET, lock
import asyncio
import threading

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
            # closing seems to interfere with errors middleware, which tries to get the value of local vars
            # and therefore queries the db
            # maybe it's not necessary to close since we just overwrite.
            # finally:
            #     db.close()
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
            msg = f'own_time={msec}ms request_id={request_id}'
            logger.info(msg)

        return response
