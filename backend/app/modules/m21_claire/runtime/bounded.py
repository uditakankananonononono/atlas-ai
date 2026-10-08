"""Bounded awaits. asyncio.wait_for waits for the cancelled coroutine's cleanup, so a body with slow cooperative cleanup can
outlive any timeout (and the lease). Here a timed-out or cancelled awaitable gets CANCEL_GRACE seconds to finish cancelling and is
then DETACHED: nobody waits for it any more. A sync tool thread is not killable either way; this bounds only our waiting,
NOT the body's lifetime: a detached model or tool body keeps running and can still touch shared objects after the timeout. There is
no isolation guarantee for a shared model/tool instance."""
from __future__ import annotations
import asyncio
from typing import Any

CANCEL_GRACE = 0.2
_DETACHED: set[asyncio.Future[Any]] = set()


def _reap(task: asyncio.Future[Any]) -> None:
    _DETACHED.discard(task)
    if not task.cancelled():
        task.exception()  # retrieved so a late failure is never reported as unhandled; its text is never used


def detach(task: asyncio.Future[Any]) -> None:
    """Stop owning a running task: keep a reference and reap any late exception so it is never reported as unhandled."""
    if task.done():
        _reap(task)
        return
    _DETACHED.add(task)
    task.add_done_callback(_reap)


async def stop(task: asyncio.Future[Any]) -> None:
    """Cancel, wait at most CANCEL_GRACE, then detach."""
    task.cancel()
    await asyncio.wait({task}, timeout=CANCEL_GRACE)
    detach(task)


async def run_bounded(aw: Any, timeout: float) -> Any:
    """Like asyncio.wait_for, but the wait after the timeout is bounded by CANCEL_GRACE. Raises asyncio.TimeoutError."""
    task = asyncio.ensure_future(aw)
    try:
        done, _ = await asyncio.wait({task}, timeout=timeout)
        if done:
            return task.result()
        await stop(task)
        raise asyncio.TimeoutError
    except asyncio.CancelledError:
        if not task.done():
            task.cancel()
        detach(task)
        raise
