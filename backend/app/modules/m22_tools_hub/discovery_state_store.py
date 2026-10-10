"""Standalone, fail-closed discovery persistence. Opt-in DurableDiscoveryService uses this store.

Only fingerprints, counters, enumerated kinds/statuses and candidate digests go
on disk. No Service objects, query text, names, errors or config are serialized.
POSIX local filesystem only. Callers must stop discovery on any StateError.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import math
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1
MAX_SOURCES = 128
MAX_QUERIES = 200
MAX_HISTORY = 200
MAX_CANDIDATES = 1000
MAX_BYTES = 4 * 1024 * 1024
MAX_COUNTER = 2**53 - 1
MAX_EPOCH = 253402300799
KINDS = frozenset({"repository", "blog", "article", "podcast", "podcast-episode", "package", "tool"})
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class StateError(Exception):
    """Fixed public error codes only, never raw OS or parser diagnostics."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _fail(code="invalid_state"):
    raise StateError(code)


def fingerprint(value: str, namespace: str) -> str:
    """Hash exact text, preserving Service's exact-query identity semantics."""
    if type(value) is not str or not value or len(value) > 8192:
        _fail("invalid_identifier")
    if namespace not in {"tenant", "source", "query"}:
        _fail("invalid_identifier")
    try:
        raw = ("m22:v1:" + namespace + "\0" + value).encode("utf-8")
    except UnicodeError:
        raise StateError("invalid_identifier") from None
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    if type(value) is not str or not _DIGEST.fullmatch(value):
        _fail()


def _integer(value, maximum=MAX_COUNTER):
    if type(value) is not int or not 0 <= value <= maximum:
        _fail()


def _number(value, maximum=MAX_EPOCH):
    if type(value) not in (int, float) or not 0 <= value <= maximum or not math.isfinite(value):
        _fail()


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        _fail()


def _ids(value):
    if type(value) is not list or len(value) > MAX_CANDIDATES:
        _fail()
    for key in value:
        _digest(key)
    if value != sorted(set(value)):
        _fail()


def _kinds(value):
    if value is None:
        return
    if type(value) is not list or len(value) > len(KINDS):
        _fail()
    if any(type(kind) is not str or kind not in KINDS for kind in value):
        _fail()
    if value != sorted(set(value)):
        _fail()


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("corrupt_state")
        result[key] = value
    return result


class DiscoveryStateStore:
    """One file per tenant, cross-process flock, bounded no-eviction ledger.

    root must be a caller-provisioned private local directory, not a shared or
    attacker-writable directory. Missing state is never silently initialized.
    provision() is ONLY for a known new tenant, not startup recovery.
    """

    def __init__(self, root: str | Path, tenant_id: str):
        self.root = Path(root)
        self.tenant = fingerprint(tenant_id, "tenant")
        self.path = self.root / ("m22_discovery_" + self.tenant + ".json")
        self.lock_path = self.root / ("m22_discovery_" + self.tenant + ".lock")

    @contextmanager
    def _locked(self):
        fd = None
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                _fail("unsafe_storage")
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        except OSError:
            raise StateError("storage_unavailable") from None
        finally:
            if fd is not None:
                os.close(fd)

    def _validate(self, state):
        _keys(state, {"schema_version", "tenant", "revision", "sources", "queries", "history"})
        if type(state["schema_version"]) is not int or state["schema_version"] != SCHEMA_VERSION:
            _fail("unsupported_version")
        if state["tenant"] != self.tenant:
            _fail("tenant_mismatch")
        _integer(state["revision"])
        sources, queries, history = state["sources"], state["queries"], state["history"]
        if type(sources) is not dict or len(sources) > MAX_SOURCES:
            _fail()
        if type(queries) is not dict or len(queries) > MAX_QUERIES:
            _fail()
        if type(history) is not list or len(history) > MAX_HISTORY:
            _fail()
        for key, stats in sources.items():
            _digest(key)
            _keys(stats, {"runs", "failures", "candidates", "last_latency_ms", "last_status", "cooldown_until"})
            for field in ("runs", "failures", "candidates"):
                _integer(stats[field])
            if stats["failures"] > stats["runs"] or stats["runs"] == 0:
                _fail()
            _number(stats["last_latency_ms"], 86400000)
            _number(stats["cooldown_until"])
            if type(stats["last_status"]) is not str or stats["last_status"] not in {"ok", "error"}:
                _fail()
        for key, item in queries.items():
            _digest(key)
            _keys(item, {"snapshot", "diff", "runs", "at", "kinds"})
            _ids(item["snapshot"])
            _integer(item["runs"])
            if item["runs"] == 0:
                _fail()
            _number(item["at"])
            _kinds(item["kinds"])
            diff = item["diff"]
            _keys(diff, {"first_run", "added", "removed"})
            if type(diff["first_run"]) is not bool or diff["first_run"] != (item["runs"] == 1):
                _fail()
            _ids(diff["added"])
            _ids(diff["removed"])
            if (set(diff["added"]) - set(item["snapshot"]) or
                    set(diff["removed"]) & set(item["snapshot"])):
                _fail()
            if diff["first_run"] and (diff["added"] or diff["removed"]):
                _fail()
        for item in history:
            _keys(item, {"query_key", "at", "kinds", "count"})
            _digest(item["query_key"])
            if item["query_key"] not in queries:
                _fail()
            _number(item["at"])
            _kinds(item["kinds"])
            _integer(item["count"], MAX_CANDIDATES)
        return state

    def _read(self):
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            raise StateError("missing_state") from None
        except OSError:
            raise StateError("storage_unavailable") from None
        try:
            with os.fdopen(fd, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    _fail("unsafe_storage")
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                _fail("state_too_large")
            envelope = json.loads(raw, object_pairs_hook=_unique_object)
            _keys(envelope, {"state", "checksum"})
            _digest(envelope["checksum"])
            state = self._validate(envelope["state"])
            if hashlib.sha256(_encode(state)).hexdigest() != envelope["checksum"]:
                _fail("checksum_mismatch")
            return state
        except (ValueError, UnicodeError, RecursionError, TypeError):
            raise StateError("corrupt_state") from None
        except OSError:
            raise StateError("storage_unavailable") from None

    def _write(self, state):
        self._validate(state)
        payload = _encode({"state": state, "checksum": hashlib.sha256(_encode(state)).hexdigest()})
        if len(payload) > MAX_BYTES:
            _fail("state_too_large")
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix=".m22-discovery-", dir=self.root)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            temporary = None
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            if self._read() != state:
                _fail("readback_mismatch")
        except OSError:
            # Replace may already have landed. Never retry blindly.
            raise StateError("commit_unverified") from None
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def provision(self):
        """Explicit first creation. Existing or corrupt files are never replaced."""
        with self._locked():
            if os.path.lexists(self.path):
                _fail("state_exists")
            state = {"schema_version": SCHEMA_VERSION, "tenant": self.tenant,
                     "revision": 0, "sources": {}, "queries": {}, "history": []}
            self._write(state)
            return copy.deepcopy(state)

    def read(self):
        with self._locked():
            return copy.deepcopy(self._read())

    def is_cooling(self, source: str, *, now: float) -> bool:
        _number(now)
        key = fingerprint(source, "source")
        state = self.read()
        return state["sources"].get(key, {}).get("cooldown_until", 0) > now

    def record_source(self, source: str, *, success: bool, candidates: int,
                      latency_ms: float, cooldown_until: float = 0):
        """Persist source outcome. Caller checks cooldown BEFORE collector execution.

        Absolute UTC epoch deadlines survive restart. A success never shortens
        an existing cooldown. Error text is deliberately not an argument.
        """
        key = fingerprint(source, "source")
        if type(success) is not bool:
            _fail()
        _integer(candidates)
        _number(latency_ms, 86400000)
        _number(cooldown_until)
        if not success and candidates != 0:
            _fail()
        with self._locked():
            state = self._read()
            if key not in state["sources"] and len(state["sources"]) >= MAX_SOURCES:
                _fail("source_capacity")
            old = state["sources"].get(key, {"runs": 0, "failures": 0, "candidates": 0, "cooldown_until": 0})
            state["sources"][key] = {
                "runs": old["runs"] + 1, "failures": old["failures"] + int(not success),
                "candidates": old["candidates"] + candidates, "last_latency_ms": latency_ms,
                "last_status": "ok" if success else "error",
                "cooldown_until": max(old["cooldown_until"], cooldown_until)}
            state["revision"] += 1
            self._write(state)
            return copy.deepcopy(state["sources"][key])

    def record_query(self, query: str, candidate_keys: list[str], *, at: float,
                     kinds: list[str] | None = None):
        """Commit a completed query snapshot and return its digest-only diff.

        candidate_keys are Service._key digests, not candidate UUIDs or names.
        Retains every admitted query identity; capacity refusal precedes change.
        """
        key = fingerprint(query, "query")
        _number(at)
        if type(candidate_keys) is not list or len(candidate_keys) > MAX_CANDIDATES:
            _fail()
        for candidate in candidate_keys:
            _digest(candidate)
        snapshot = sorted(set(candidate_keys))
        if kinds is not None:
            if type(kinds) is not list or any(type(k) is not str or k not in KINDS for k in kinds):
                _fail()
            kinds = sorted(set(kinds))
        with self._locked():
            state = self._read()
            previous = state["queries"].get(key)
            if previous is None and len(state["queries"]) >= MAX_QUERIES:
                _fail("query_capacity")
            before = set(previous["snapshot"]) if previous is not None else set()
            diff = {"first_run": previous is None,
                    "added": sorted(set(snapshot) - before) if previous is not None else [],
                    "removed": sorted(before - set(snapshot))}
            state["queries"][key] = {"snapshot": snapshot, "diff": diff,
                                     "runs": previous["runs"] + 1 if previous else 1,
                                     "at": at, "kinds": kinds}
            state["history"] = (state["history"] + [{"query_key": key, "at": at,
                                                      "kinds": kinds, "count": len(snapshot)}])[-MAX_HISTORY:]
            state["revision"] += 1
            self._write(state)
            return copy.deepcopy(diff)
