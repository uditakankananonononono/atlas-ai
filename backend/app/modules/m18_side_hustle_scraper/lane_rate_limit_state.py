"""Standalone, single-writer durable pacing snapshot contract (not wired).

Restoration failures raise StateRejected: callers MUST deny collection rather
than instantiate a fresh limiter. Integrity checks detect accidental corruption,
not a malicious writer or rollback. See the accompanying contract for limits.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Protocol

VERSION = 1
MAX_BYTES = 1_048_576
MAX_HOSTS = 1024
MAX_COUNTER = (1 << 63) - 1
MAX_INTERVAL_SECONDS = 604800
MAX_RETENTION_SECONDS = 2592000


class StateRejected(ValueError):
    """Snapshot is unusable. This is a deny signal, never an empty-state result."""


class StateFields(Protocol):
    """Explicit structural input matching existing lane_rate_limit.HostState."""
    last_request_at: datetime | None
    interval: float
    consecutive_failures: int
    circuit_open_until: datetime | None
    total_requests: int
    total_failures: int


@dataclass(frozen=True)
class PacingState:
    last_request_at: datetime | None
    interval: float
    consecutive_failures: int
    circuit_open_until: datetime | None
    total_requests: int
    total_failures: int


@dataclass(frozen=True)
class RestoredSnapshot:
    tenant_id: str
    saved_at: datetime
    expires_at: datetime
    states: Mapping[str, PacingState]


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise StateRejected("timezone-aware timestamp required")
    try:
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise StateRejected("timestamp outside supported range") from exc


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise StateRejected("invalid timestamp")
    try:
        return _aware(datetime.fromisoformat(value))
    except (ValueError, TypeError, OverflowError) as exc:
        raise StateRejected("invalid timestamp") from exc


def _identifier(value: object, limit: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= limit:
        raise StateRejected("invalid identifier")
    if any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise StateRejected("invalid identifier")
    return value


def _keys(value: object, expected: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise StateRejected("invalid schema")
    return value


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, OverflowError) as exc:
        raise StateRejected("invalid JSON value") from exc


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise StateRejected("duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise StateRejected("non-finite JSON value")


def _counter(value: object) -> int:
    if type(value) is not int or not 0 <= value <= MAX_COUNTER:
        raise StateRejected("invalid counter")
    return value


def _state(value: object, saved: datetime, expires: datetime) -> PacingState:
    row = _keys(value, {"last_request_at", "interval", "consecutive_failures",
                        "circuit_open_until", "total_requests", "total_failures"})
    interval = row["interval"]
    if type(interval) not in (int, float) or not 0 <= interval <= MAX_INTERVAL_SECONDS or not math.isfinite(interval):
        raise StateRejected("invalid interval")
    last = None if row["last_request_at"] is None else _timestamp(row["last_request_at"])
    until = None if row["circuit_open_until"] is None else _timestamp(row["circuit_open_until"])
    if last is not None and last > saved:
        raise StateRejected("request timestamp after snapshot")
    # Never discard a wait through TTL expiry. Expiry itself is a deny signal.
    try:
        if last is not None and last + timedelta(seconds=interval) > expires:
            raise StateRejected("pacing deadline beyond expiry")
    except OverflowError as exc:
        raise StateRejected("pacing timestamp overflow") from exc
    if until is not None and until > expires:
        raise StateRejected("circuit deadline beyond expiry")
    consecutive = _counter(row["consecutive_failures"])
    requests = _counter(row["total_requests"])
    failures = _counter(row["total_failures"])
    if consecutive > failures:
        raise StateRejected("inconsistent failure counters")
    return PacingState(last, float(interval), consecutive, until, requests, failures)


def encode_snapshot(tenant_id: str, states: Mapping[str, StateFields], *,
                    now: datetime, expires_at: datetime) -> bytes:
    """Serialize all states without pruning; excess size is rejected, not evicted."""
    tenant_id = _identifier(tenant_id, 256)
    saved, expires = _aware(now), _aware(expires_at)
    if not 0 < (expires - saved).total_seconds() <= MAX_RETENTION_SECONDS:
        raise StateRejected("invalid retention window")
    if len(states) > MAX_HOSTS:
        raise StateRejected("too many hosts")
    rows = {}
    for host, state in states.items():
        host = _identifier(host, 253)
        rows[host] = {
            "last_request_at": None if state.last_request_at is None else _aware(state.last_request_at).isoformat(),
            "interval": state.interval,
            "consecutive_failures": state.consecutive_failures,
            "circuit_open_until": None if state.circuit_open_until is None else _aware(state.circuit_open_until).isoformat(),
            "total_requests": state.total_requests,
            "total_failures": state.total_failures,
        }
        rows[host]["interval"] = _state(rows[host], saved, expires).interval
    payload = {"version": VERSION, "tenant_id": tenant_id,
               "saved_at": saved.isoformat(), "expires_at": expires.isoformat(), "states": rows}
    raw = _canonical({"payload": payload, "sha256": hashlib.sha256(_canonical(payload)).hexdigest()})
    if len(raw) > MAX_BYTES:
        raise StateRejected("snapshot too large")
    # Read back our serialized representation through the same strict decoder.
    decode_snapshot(raw, tenant_id=tenant_id, now=saved)
    return raw


def decode_snapshot(raw: bytes, *, tenant_id: str, now: datetime) -> RestoredSnapshot:
    """Return a completely validated snapshot, or raise without partial state."""
    tenant_id, current = _identifier(tenant_id, 256), _aware(now)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise StateRejected("invalid snapshot size")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise StateRejected("corrupt snapshot") from exc
    envelope = _keys(document, {"payload", "sha256"})
    checksum = envelope["sha256"]
    if not isinstance(checksum, str) or len(checksum) != 64:
        raise StateRejected("invalid checksum")
    try:
        expected = hashlib.sha256(_canonical(envelope["payload"])).hexdigest()
        if not hmac.compare_digest(checksum.encode("ascii"), expected.encode("ascii")):
            raise StateRejected("checksum mismatch")
    except (UnicodeError, RecursionError) as exc:
        raise StateRejected("invalid checksum payload") from exc
    payload = _keys(envelope["payload"], {"version", "tenant_id", "saved_at", "expires_at", "states"})
    if type(payload["version"]) is not int or payload["version"] != VERSION:
        raise StateRejected("unsupported snapshot version")
    if _identifier(payload["tenant_id"], 256) != tenant_id:
        raise StateRejected("tenant mismatch")
    saved, expires = _timestamp(payload["saved_at"]), _timestamp(payload["expires_at"])
    if saved > current:
        raise StateRejected("clock rollback or future snapshot")
    if not 0 < (expires - saved).total_seconds() <= MAX_RETENTION_SECONDS or current >= expires:
        raise StateRejected("expired or invalid retention window")
    rows = payload["states"]
    if not isinstance(rows, dict) or len(rows) > MAX_HOSTS:
        raise StateRejected("invalid host count")
    states = {_identifier(host, 253): _state(row, saved, expires) for host, row in rows.items()}
    return RestoredSnapshot(tenant_id, saved, expires, MappingProxyType(states))


def read_snapshot(path: Path, *, tenant_id: str, now: datetime) -> RestoredSnapshot:
    """Bounded no-symlink read. Missing files deny; explicit initialization is separate."""
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise StateRejected("snapshot is not a regular file")
        with os.fdopen(fd, "rb") as stream:
            fd = None
            raw = stream.read(MAX_BYTES + 1)
        return decode_snapshot(raw, tenant_id=tenant_id, now=now)
    except OSError as exc:
        raise StateRejected("snapshot unavailable") from exc
    finally:
        if fd is not None:
            os.close(fd)


def write_snapshot(path: Path, tenant_id: str, states: Mapping[str, StateFields], *,
                   now: datetime, expires_at: datetime) -> RestoredSnapshot:
    """Fsync temp, atomic replace, fsync directory, then validate disk readback.

    A post-replace failure may leave the new file installed. It still raises;
    the caller must stop collection and reconcile, not assume no write occurred.
    The caller supplies an existing trusted private directory and serializes writers.
    """
    raw = encode_snapshot(tenant_id, states, now=now, expires_at=expires_at)
    path = Path(path)
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".pacing-", dir=path.parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        result = read_snapshot(path, tenant_id=tenant_id, now=now)
        # The decoded record must match the exact persisted snapshot.
        if encode_snapshot(result.tenant_id, result.states, now=result.saved_at,
                           expires_at=result.expires_at) != raw:
            raise StateRejected("readback mismatch")
        return result
    except OSError as exc:
        raise StateRejected("durable write unavailable") from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise StateRejected("temporary cleanup unavailable") from exc
