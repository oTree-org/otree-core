from functools import partial
from typing import Callable

import trio
from trio import Nursery

from ..typing import AsyncContext


class Context(AsyncContext):
    def __init__(self, nursery: Nursery):
        self.nursery = nursery

    sleep = staticmethod(trio.sleep)

    async def start_task(self, fn: Callable, *args, **kwargs):
        return await self.nursery.start(_cancellable, partial(fn, *args, **kwargs))


async def _cancellable(
    task_fn: Callable,
    task_status = trio.TASK_STATUS_IGNORED,
):
    with trio.CancelScope() as scope:
        task_status.started(scope)
        await task_fn()
