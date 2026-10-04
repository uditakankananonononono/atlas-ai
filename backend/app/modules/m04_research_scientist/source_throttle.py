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
import stat
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

MIN_INTERVAL = {"arxiv": 3.0, "pubmed": 0.4}


class ThrottleStateError(RuntimeError):
    """State dir or stamp is unsafe; the request is refused rather than sent unthrottled."""


class ThrottleBusy(RuntimeError):
    """Too many callers already queued for this source."""


MAX_QUEUED = 3  # callers allowed to wait per source in this process; more are refused


def _private_dir(base: Path) -> Path:
    path = base
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise ThrottleStateError("state dir is not a plain directory")
    if st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ThrottleStateError("state dir must be owned by this user and private (0700)")
    return path


class SourceThrottle:
    def __init__(self, clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep,
                 state_dir: str | Path | None = None) -> None:
        self._clock, self._sleep = clock, sleep
        configured = state_dir or os.getenv("ATLAS_COLLECTOR_STATE_DIR")
        self._base = Path(configured) if configured else Path(tempfile.gettempdir()) / f"atlas-collector-{os.getuid()}"
        self._threads: dict[str, threading.Lock] = {}
        self._queued: dict[str, int] = {}
        self._guard = threading.Lock()

    def run(self, source: str, fn: Callable[[], object]):
        interval = MIN_INTERVAL[source]
        with self._guard:
            if self._queued.get(source, 0) >= MAX_QUEUED + 1:
                raise ThrottleBusy("collector queue full")
            self._queued[source] = self._queued.get(source, 0) + 1
            tlock = self._threads.setdefault(source, threading.Lock())
        try:
            with tlock:
                return self._run_locked(source, interval, fn)
        finally:
            with self._guard:
                self._queued[source] -= 1

    def _run_locked(self, source, interval, fn):
        directory = _private_dir(self._base)
        try:
            fd = os.open(directory / f"{source}.stamp", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        except OSError as exc:
            raise ThrottleStateError("cannot open stamp file safely") from exc
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
                raise ThrottleStateError("stamp file must be a private regular file owned by this user")
            fcntl.flock(fd, fcntl.LOCK_EX)  # blocks other processes: one in-flight request per source
            raw = os.pread(fd, 64, 0).decode("ascii", "ignore").strip()
            now = self._clock()
            try:
                last = float(raw) if raw else None
            except ValueError:
                last = now  # corrupt stamp: assume a request just happened, wait a full interval
            if last is not None and (last > now or last != last):
                last = now  # future/NaN stamp: conservative full wait, never zero
            if last is not None:
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
