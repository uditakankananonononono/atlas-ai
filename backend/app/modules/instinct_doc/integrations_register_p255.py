"""P255|L202 - "Output: External tool integrations,".

A bounded catalog of DECLARED tool/API integrations per project. Pure stdlib,
deterministic. It performs no live integration call and never claims an
integration is connected or verified. evidence_ref is recorded, never resolved.
"""
from __future__ import annotations

from dataclasses import dataclass

STATUSES = ("declared", "planned", "active", "deprecated")
FIELDS = ("id", "project_id", "name", "purpose", "status", "evidence_ref")
REQUIRED = ("id", "project_id", "name", "purpose", "status")
TEXT_LIMITS = {"id": 64, "project_id": 64, "name": 64, "purpose": 256, "evidence_ref": 128}
MAX_PROJECTS = 1024
MAX_INTEGRATIONS_PER_PROJECT = 256


@dataclass(frozen=True)
class Register:
    entries: tuple = ()  # (id, project_id, name, purpose, status, evidence_ref)


def create_register() -> Register:
    return Register()


def _err(code: str) -> ValueError:
    return ValueError("P255:" + code)


def _validate(entry) -> tuple:
    if not isinstance(entry, dict):
        raise _err("bad_type:entry")
    if any(k not in FIELDS for k in entry):
        raise _err("unknown_fields:entry")
    for name in REQUIRED:
        if name not in entry:
            raise _err("empty_field:" + name)
    values = dict(entry)
    values.setdefault("evidence_ref", "")
    for name in FIELDS:
        v = values[name]
        if isinstance(v, bool) or not isinstance(v, str):
            raise _err("bad_type:" + name)
    for name in REQUIRED:
        if not values[name].strip():
            raise _err("empty_field:" + name)
    if not values["evidence_ref"].strip():
        values["evidence_ref"] = ""
    for name, limit in TEXT_LIMITS.items():
        if len(values[name]) > limit:
            raise _err("text_too_long:" + name)
    if values["status"] not in STATUSES:
        raise _err("bad_status:" + values["status"])
    return tuple(values[name] for name in FIELDS)


def append(register: Register, entry) -> Register:
    if not isinstance(register, Register):
        raise _err("bad_type:register")
    row = _validate(entry)
    if any(r[0] == row[0] for r in register.entries):
        raise _err("duplicate_id:" + row[0])
    mine = [r for r in register.entries if r[1] == row[1]]
    if any(r[2] == row[2] for r in mine):
        raise _err("duplicate_name:" + row[2])
    if len(mine) >= MAX_INTEGRATIONS_PER_PROJECT:
        raise _err("limit_exceeded:integrations_per_project")
    if not mine and len({r[1] for r in register.entries}) >= MAX_PROJECTS:
        raise _err("limit_exceeded:projects")
    return Register(register.entries + (row,))


def render(register: Register, project_id=None) -> str:
    if not isinstance(register, Register):
        raise _err("bad_type:register")
    if project_id is None:
        ids = sorted({r[1] for r in register.entries})
    else:
        if isinstance(project_id, bool) or not isinstance(project_id, str):
            raise _err("bad_type:project_id")
        if not any(r[1] == project_id for r in register.entries):
            raise _err("unknown_project:" + project_id)
        ids = [project_id]
    lines = []
    for pid in ids:
        rows = sorted((r for r in register.entries if r[1] == pid), key=lambda r: r[2])
        lines.append("project %s (%d integrations)" % (pid, len(rows)))
        for r in rows:
            ev = "[%s]" % r[5] if r[5] else "UNVERIFIED"
            lines.append("%s %s %s %s" % (r[2], r[4], r[3], ev))
    return "\n".join(lines)
