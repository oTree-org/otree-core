from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from time import time
from starlette.requests import Request
import logging
from otree.database import db, NEW_SCOPE_EACH_REQUEST
from otree.common import _SECRET, lock
import asyncio
import threading

logger = logging.getLogger('otree.perf')


lock2 = asyncio.Lock()


class CommitTransactionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        async with lock2:
            if not NEW_SCOPE_EACH_REQUEST:
                db.new_session()
            try:
                response = await call_next(request)
                db.commit()
            except Exception:
                db.rollback()
                raise
            # closing seems to interfere with errors middleware, which tries to get the value of local vars
            # and therefore queries the db
            # maybe it's not necessary to close since we just overwrite.
            # finally:
            #     db.close()
            return response


class PerfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time()

        response = await call_next(request)

        # heroku has 'X-Request-ID'
        request_id = request.headers.get('X-Request-ID')
        if request_id:
            # only log this info on Heroku
            elapsed = time() - start
            msec = int(elapsed * 1000)
            msg = f'own_time={msec}ms request_id={request_id}'
            logger.info(msg)

        return response


class CheckDBMiddleware:
    synced = None

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not CheckDBMiddleware.synced:
            # very fast, 0.01-0.02 seconds for the whole check
            missing_tables = missing_db_tables()
            if missing_tables:
                listed_tables = missing_tables[:3]
                unlisted_tables = missing_tables[3:]
                msg = (
                    "Your database is not ready. Try resetting the database "
                    "(Missing tables for {}, and {} other models). "
                ).format(', '.join(listed_tables), len(unlisted_tables))
                return HttpResponseServerError(msg)
            else:
                CheckDBMiddleware.synced = True
        return self.get_response(request)


middlewares = [
    Middleware(PerfMiddleware),
    Middleware(CommitTransactionMiddleware),
    Middleware(SessionMiddleware, secret_key=_SECRET),
]
