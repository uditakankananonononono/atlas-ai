"""Sub-agent delegation with bounded concurrency, ported from meemee `team.py`
(C4 meemee-merge).

Semantics preserved from meemee@50e7605: 1..32 goals, semaphore-bounded fan-out,
optional cancellation, owner-isolation check on the child run signature, no
retries after child errors (the child may already have written), per-goal
reports, and cleanup shielding so a cancelled sibling still finishes closing.
"""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any


class AgentTeam:
    """Runs independent delegated goals concurrently and preserves per-agent reports."""

    def __init__(self, factory: Callable[[], Any], max_concurrency: int = 4):
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self.factory = factory
        self.limit = asyncio.Semaphore(max_concurrency)

    async def delegate(self, goals: list[str], cancel=None, *, owner_id: str) -> list[dict[str, Any]]:
        if not goals or len(goals) > 32:
            raise ValueError("delegate between 1 and 32 goals")

        async def one(index: int, goal: str) -> dict[str, Any]:
            async with self.limit:
                child = None
                try:
                    if cancel is not None and cancel.is_set():
                        return {"index": index, "goal": goal, "ok": False, "error": "delegation cancelled"}
                    child = self.factory()
                    if inspect.isawaitable(child):
                        child = await child
                    parameters = inspect.signature(child.run).parameters
                    options = {}
                    if "cancel" in parameters:
                        options["cancel"] = cancel
                    if "owner_id" in parameters:
                        options["owner_id"] = owner_id
                    elif owner_id != "default":
                        raise ValueError("child agent does not support owner isolation")
                    # Never retry a child after a TypeError: it may already have written.
                    report = await child.run(goal, **options)
                    if hasattr(report, "model_dump"):
                        report = report.model_dump()
                    return {"index": index, "goal": goal, "ok": True, "report": report}
                except (OSError, ValueError, RuntimeError) as exc:
                    return {"index": index, "goal": goal, "ok": False, "error": str(exc)}
                finally:
                    close = getattr(child, "aclose", None)
                    if close is not None:
                        # A sibling failure may cancel this task after close has
                        # begun. Keep its finalizer alive and join it before exit.
                        cleanup = asyncio.ensure_future(close())
                        try:
                            await asyncio.shield(cleanup)
                        except asyncio.CancelledError:
                            await cleanup
                            raise
                    elif getattr(child, "owns_model", False):
                        close_model = getattr(getattr(child, "model", None), "aclose", None)
                        if close_model is not None:
                            await close_model()

        tasks = [asyncio.ensure_future(one(index, goal)) for index, goal in enumerate(goals)]
        try:
            return await asyncio.gather(*tasks)
        except BaseException:
            # Propagate the original error only after every sibling has stopped
            # and completed its own resource cleanup. Never replay a child.
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
