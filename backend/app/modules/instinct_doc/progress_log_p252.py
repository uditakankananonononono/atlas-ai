"""P252|L199 - "Progress log by task." (output-format section, after "Provide:").

Pure stdlib, deterministic output artifact. It records and renders supplied
entries only. It does not track real work, verify claims, resolve source_ref,
read a clock, or ever emit a "completed" entry by itself.
"""
from __future__ import annotations

from dataclasses import dataclass

STATUSES = ("started", "progress", "blocked", "completed", "failed", "note")
TERMINAL = ("completed", "failed")
FIELDS = ("id", "task_id", "seq", "status", "message", "source_ref")
TEXT_LIMITS = {"id": 64, "task_id": 64, "message": 256, "source_ref": 128}
MAX_TASKS = 1024
MAX_ENTRIES_PER_TASK = 4096


@dataclass(frozen=True)
class ProgressLog:
    entries: tuple = ()  # tuple of (id, task_id, seq, status, message, source_ref)


def create_log() -> ProgressLog:
    return ProgressLog()


def _err(code: str) -> ValueError:
    return ValueError("P252:" + code)


def _validate(entry) -> tuple:
    if not isinstance(entry, dict):
        raise _err("bad_type:entry")
    extra = sorted(str(k) for k in entry if k not in FIELDS)
    if extra:
        raise _err("unknown_fields:entry")
    for name in FIELDS:
        if name not in entry:
            raise _err("empty_field:" + name)
    for name in FIELDS:
        value = entry[name]
        if isinstance(value, bool):
            raise _err("bad_type:" + name)
        if name == "seq":
            if not isinstance(value, int):
                raise _err("bad_type:seq")
        elif not isinstance(value, str):
            raise _err("bad_type:" + name)
    for name in ("id", "task_id", "status", "message", "source_ref"):
        if not entry[name].strip():
            raise _err("empty_field:" + name)
    for name, limit in TEXT_LIMITS.items():
        if len(entry[name]) > limit:
            raise _err("text_too_long:" + name)
    if entry["status"] not in STATUSES:
        raise _err("bad_status:" + entry["status"])
    return tuple(entry[name] for name in FIELDS)


def append(log: ProgressLog, entry) -> ProgressLog:
    if not isinstance(log, ProgressLog):
        raise _err("bad_type:log")
    row = _validate(entry)
    eid, task_id, seq, status = row[0], row[1], row[2], row[3]
    if any(r[0] == eid for r in log.entries):
        raise _err("duplicate_id:" + eid)
    mine = [r for r in log.entries if r[1] == task_id]
    if mine and mine[-1][3] in TERMINAL:
        raise _err("task_closed:" + task_id)
    if seq < 0 or (mine and seq <= max(r[2] for r in mine)):
        raise _err("non_monotonic_seq:" + task_id)
    if len(mine) >= MAX_ENTRIES_PER_TASK:
        raise _err("limit_exceeded:entries_per_task")
    if not mine and len({r[1] for r in log.entries}) >= MAX_TASKS:
        raise _err("limit_exceeded:tasks")
    return ProgressLog(log.entries + (row,))


def task_status(log: ProgressLog, task_id) -> str:
    if not isinstance(log, ProgressLog) or not isinstance(task_id, str):
        return "unknown"
    mine = [r for r in log.entries if r[1] == task_id]
    if not mine:
        return "unknown"
    last = mine[-1][3]
    return last if last in TERMINAL else "open"


def render(log: ProgressLog, task_id=None) -> str:
    if not isinstance(log, ProgressLog):
        raise _err("bad_type:log")
    if task_id is None:
        ids = sorted({r[1] for r in log.entries})
    else:
        if not isinstance(task_id, str) or isinstance(task_id, bool):
            raise _err("bad_type:task_id")
        if task_status(log, task_id) == "unknown":
            raise _err("unknown_task:" + task_id)
        ids = [task_id]
    lines = []
    for tid in ids:
        rows = sorted((r for r in log.entries if r[1] == tid), key=lambda r: r[2])
        lines.append("task %s (%d entries, %s)" % (tid, len(rows), task_status(log, tid)))
        for r in rows:
            lines.append("%d %s %s [%s]" % (r[2], r[3], r[4], r[5]))
    return "\n".join(lines)
