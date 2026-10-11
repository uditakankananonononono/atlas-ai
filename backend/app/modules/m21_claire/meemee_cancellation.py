"""Cooperative cancellation and bounded graceful shutdown, ported from meemee
`cancellation.py` and `shutdown.py` (C4 meemee-merge).

Verbatim semantics from meemee@50e7605: thread-safe per-job cancellation events
and an async run gate that drains active work within a bounded timeout.
"""
from __future__ import annotations

import asyncio
import threading


class CancellationRegistry:
    """Thread-safe cooperative cancellation registry for active local jobs."""

    def __init__(self):
        self._events: dict[str, threading.Event] = {}
        self._lock = threading.RLock()

    def register(self, job_id: str) -> threading.Event:
        with self._lock:
            if job_id in self._events:
                raise ValueError(f"job already registered: {job_id}")
            event = threading.Event()
            self._events[job_id] = event
            return event

    def request(self, job_id: str) -> bool:
        with self._lock:
            event = self._events.get(job_id)
            if event is None:
                return False
            event.set()
            return True

    def unregister(self, job_id: str) -> None:
        with self._lock:
            self._events.pop(job_id, None)


class RunGate:
    """Tracks active runs and supports bounded graceful shutdown."""

    def __init__(self):
        self._active = 0
        self._accepting = True
        self._condition = asyncio.Condition()

    @property
    def accepting(self) -> bool:
        return self._accepting

    @property
    def active(self) -> int:
        return self._active

    async def enter(self) -> None:
        async with self._condition:
            if not self._accepting:
                raise RuntimeError("server is draining")
            self._active += 1

    async def leave(self) -> None:
        async with self._condition:
            if self._active == 0:
                raise RuntimeError("run gate underflow")
            self._active -= 1
            if self._active == 0:
                self._condition.notify_all()

    async def drain(self, timeout: float) -> bool:
        async with self._condition:
            self._accepting = False
            if self._active == 0:
                return True
            try:
                await asyncio.wait_for(self._condition.wait_for(lambda: self._active == 0), timeout)
                return True
            except (TimeoutError, asyncio.TimeoutError):
                return False
