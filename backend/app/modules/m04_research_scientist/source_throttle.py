"""Cross-process spacing for public literature APIs (single host).

Provider limits (published terms, fetched 2026-10-04):
- arXiv legacy API: at most one request every 3 s, one connection at a time, across ALL
  machines under your control (https://info.arxiv.org/help/api/tou.html).
- NCBI E-utilities: at most 3 requests/s without an API key
  (https://www.ncbi.nlm.nih.gov/books/NBK25497/).

SCOPE: an flock on a state file under ATLAS_COLLECTOR_STATE_DIR (default: system temp dir)
serializes and spaces requests across threads AND processes on ONE host sharing that
directory. It does NOT coordinate multiple machines or containers with separate
filesystems; those need a shared lock (for example a database or Redis lock) that does not
exist here. Until then, run exactly one collector host. No scheduler uses this yet.
"""
from __future__ import annotations

import fcntl
import os
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

MIN_INTERVAL = {"arxiv": 3.0, "pubmed": 0.4}


class SourceThrottle:
    def __init__(self, clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep,
                 state_dir: str | Path | None = None) -> None:
        self._clock, self._sleep = clock, sleep
        self._dir = Path(state_dir or os.getenv("ATLAS_COLLECTOR_STATE_DIR") or tempfile.gettempdir())
        self._threads: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def run(self, source: str, fn: Callable[[], object]):
        interval = MIN_INTERVAL[source]
        with self._guard:
            tlock = self._threads.setdefault(source, threading.Lock())
        path = self._dir / f"atlas-collector-{source}.stamp"
        with tlock:
            fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)  # blocks other processes: one in-flight request per source
                raw = os.pread(fd, 64, 0).decode("ascii", "ignore").strip()
                try:
                    last = float(raw)
                except ValueError:
                    last = None
                now = self._clock()
                if last is not None and last <= now:  # a future stamp is clock skew: ignore it
                    wait = interval - (now - last)
                    if wait > 0:
                        self._sleep(wait)
                try:
                    return fn()
                finally:
                    os.ftruncate(fd, 0)
                    os.pwrite(fd, repr(self._clock()).encode(), 0)
            finally:
                os.close(fd)  # releases the flock


THROTTLE = SourceThrottle()
