"""P255|L202 - "Output: External tool integrations,".

A bounded catalog of DECLARED tool/API integrations per project. Pure stdlib,
deterministic. It performs no live integration call and never claims an
integration is connected or verified. evidence_ref is recorded, never resolved.
"""
from __future__ import annotations

import unicodedata
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


def _has_control(text: str) -> bool:
    return any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in text)


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
    for name in FIELDS:
        if _has_control(values[name]):
            raise _err("bad_chars:" + name)
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


def bind_local_evidence(register, root, bindings):
    """Read and hash adapter/use artifacts; never turn local receipts into live use.

    Every integration appears, including missing bindings. References describe
    operator scope, not discovered semantic coverage or authenticated execution.
    """
    from pathlib import Path
    from .repo_evidence import EvidenceError, safe_file, digest
    if not isinstance(register, Register):
        raise _err('bad_type:register')
    if type(bindings) is not list or len(bindings) > 4096:
        raise _err('bad_type:bindings')
    root_error = None
    try:
        root = Path(root).resolve()
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        root_error = str(exc)[:200]
    known = {row[0] for row in register.entries}
    by_id = {}
    for item in bindings:
        if type(item) is not dict or set(item) != {'entry_id', 'adapter_path', 'use_evidence_path', 'row_ids', 'project_ids'}:
            raise _err('bad_fields:binding')
        ident = item['entry_id']
        if not isinstance(ident, str) or ident not in known or ident in by_id:
            raise _err('unknown_or_duplicate:entry_id')
        for key in ('adapter_path', 'use_evidence_path'):
            if not isinstance(item[key], str):
                raise _err('bad_type:' + key)
        for key in ('row_ids', 'project_ids'):
            v = item[key]
            if type(v) is not list or len(v) > 1000 or not all(isinstance(x, str) and x.strip() and len(x) <= 128 and not _has_control(x) for x in v) or len(set(v)) != len(v):
                raise _err('bad_type:' + key)
        by_id[ident] = item
    rows = []
    for row in register.entries:
        ident, project, name, purpose, declared_status, evidence_ref = row
        item = by_id.get(ident)
        out = {'entry_id': ident, 'project_id': project, 'name': name,
               'declared_status': declared_status, 'status': 'UNVERIFIED',
               'adapter_sha256': None, 'use_evidence_sha256': None,
               'live_working_use_verified': False, 'row_ids': [], 'project_ids': [project],
               'reason': 'No local adapter/use binding', 'file_errors': {}}
        if item:
            out['row_ids'] = sorted(item['row_ids'])
            out['project_ids'] = sorted(set(item['project_ids'] + [project]))
            for field, target in [('adapter_path', 'adapter_sha256'), ('use_evidence_path', 'use_evidence_sha256')]:
                try:
                    if root_error:
                        raise EvidenceError('root resolution failed: ' + root_error)
                    out[target] = digest(safe_file(root, item[field]).read_bytes()) if item[field] else None
                except (EvidenceError, OSError, ValueError, RuntimeError, TypeError) as exc:
                    out[target] = None
                    out['file_errors'][field] = type(exc).__name__ + ': ' + str(exc)[:200]
            if out['adapter_sha256'] and out['use_evidence_sha256']:
                out['status'] = 'DECLARED-ONLY'
                out['reason'] = 'Adapter and use artifact bytes exist; receipt authenticity and live use unchecked'
        rows.append(out)
    return {'entries': rows, 'unbound_entry_ids': sorted(known - set(by_id)),
            'counts': {status: sum(row['status'] == status for row in rows) for status in ('DECLARED-ONLY', 'UNVERIFIED')},
            'integration_references': {row['entry_id']: {'project_ids': row['project_ids'], 'row_ids': row['row_ids']} for row in rows},
            'working_external_tool_count': None,
            'boundary': 'Check-then-read path/size changes are not atomically fenced; use immutable trusted checkouts. Local hashes and operator-declared reference mappings only; no live call, connection, receipt authenticity or working-use certification.'}
