import asyncio
from typing import Callable

from ..typing import AsyncContext


class Context(AsyncContext):
    sleep = staticmethod(asyncio.sleep)

    async def start_task(self, fn: Callable, *args, **kwargs):
        return asyncio.create_task(fn(*args, **kwargs))
