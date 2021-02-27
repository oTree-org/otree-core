import asyncio

import starlette.exceptions
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.types import Message, Receive, Scope, Send


class ExceptionMiddleware(starlette.exceptions.ExceptionMiddleware):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """oTree just removed the 'from None'. everything else is the same
        Need this until https://github.com/encode/starlette/issues/1114 is fixed
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def sender(message: Message) -> None:
            nonlocal response_started

            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, sender)
        except Exception as exc:
            handler = None

            if isinstance(exc, HTTPException):
                handler = self._status_handlers.get(exc.status_code)

            if handler is None:
                handler = self._lookup_exception_handler(exc)

            if handler is None:
                # oTree changed this part only
                raise exc  # from None

            if response_started:
                msg = "Caught handled exception, but response already started."
                raise RuntimeError(msg) from exc

            request = Request(scope, receive=receive)
            if asyncio.iscoroutinefunction(handler):
                response = await handler(request, exc)
            else:
                response = await run_in_threadpool(handler, request, exc)
            await response(scope, receive, sender)
