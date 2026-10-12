"""P253|L200 - "Output: Repository links/paths," (output-format section).

Pure stdlib, deterministic output artifact. It RECORDS supplied repository
links/paths per project, validated and deduplicated. It never resolves a link,
never fetches, never reads a filesystem, and never marks anything verified:
every recorded entry stays UNVERIFIED.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

FIELDS = ("id", "project_id", "kind", "value", "source_ref")
KINDS = ("link", "path")
TEXT_LIMITS = {"id": 64, "project_id": 64, "value": 512, "source_ref": 128}
MAX_ENTRIES = 4096

FORBIDDEN_CATEGORIES = ("Cc", "Zl", "Zp")

BOUNDARY = ("Declared repository link/path register only. It records caller-supplied values; "
            "it never resolves links, fetches content or reads a filesystem, so recording is "
            "not proof that any repository exists, is hosted or belongs to the project.")


@dataclass(frozen=True)
class RepoRegister:
    entries: tuple = ()  # tuple of (id, project_id, kind, value, normalized, source_ref)


def create_register() -> RepoRegister:
    return RepoRegister()


def _err(code: str) -> ValueError:
    return ValueError("P253:" + code)


def _valid_link(value: str) -> bool:
    try:
        raw = value.strip()
        split = urlsplit(raw)
        authority = raw.partition("://")[2]
        for sep in "/?#":
            authority = authority.split(sep, 1)[0]
        if any(c.isspace() for c in authority):
            return False
        split.port  # raises ValueError for a non-numeric or out-of-range port
        return split.scheme == "https" and bool(split.hostname) and not split.username \
            and not split.password and not split.query and not split.fragment
    except ValueError:
        return False


def _normalize_link(value: str) -> str:
    split = urlsplit(value.strip())
    path = split.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"https://{(split.hostname or '').lower()}{path.rstrip('/')}"


def _valid_path(value: str) -> bool:
    if value.startswith("/") or "\\" in value:
        return False
    parts = value.split("/")
    return all(p not in ("", ".", "..") for p in parts)


def _normalize(value: str, kind: str) -> str:
    return _normalize_link(value) if kind == "link" else value


def _validate(entry) -> tuple:
    if not isinstance(entry, dict) or type(entry) is not dict:
        raise _err("bad_type:entry")
    if any(k not in FIELDS for k in entry):
        raise _err("unknown_fields:entry")
    for name in FIELDS:
        if name not in entry:
            raise _err("empty_field:" + name)
    for name in FIELDS:
        if isinstance(entry[name], bool) or not isinstance(entry[name], str):
            raise _err("bad_type:" + name)
    for name in ("id", "project_id", "kind", "value", "source_ref"):
        if not entry[name].strip():
            raise _err("empty_field:" + name)
    for name in ("id", "project_id", "value", "source_ref"):
        if any(unicodedata.category(c) in FORBIDDEN_CATEGORIES for c in entry[name]):
            raise _err("control_chars:" + name)
    for name, limit in TEXT_LIMITS.items():
        if len(entry[name]) > limit:
            raise _err("text_too_long:" + name)
    kind = entry["kind"]
    if kind not in KINDS:
        raise _err("bad_kind:" + kind)
    value = entry["value"]
    if kind == "link" and not _valid_link(value):
        raise _err("bad_link:" + value)
    if kind == "path" and not _valid_path(value):
        raise _err("bad_path:" + value)
    return (entry["id"], entry["project_id"], kind, value, _normalize(value, kind),
            entry["source_ref"])


def add_entry(register: RepoRegister, entry) -> RepoRegister:
    if not isinstance(register, RepoRegister):
        raise _err("bad_type:register")
    row = _validate(entry)
    eid, project_id, kind, _, normalized, _ = row
    if any(r[0] == eid for r in register.entries):
        raise _err("duplicate_id:" + eid)
    for r in register.entries:
        if r[1] == project_id and r[2] == kind and r[4] == normalized:
            raise _err("duplicate_entry:" + r[0])
    if len(register.entries) >= MAX_ENTRIES:
        raise _err("limit_exceeded:entries")
    return RepoRegister(register.entries + (row,))


def _row_dict(row) -> dict:
    return {"id": row[0], "project_id": row[1], "kind": row[2], "value": row[3],
            "normalized": row[4], "source_ref": row[5],
            "verification": "UNVERIFIED", "resolved": False, "fetched": False}


def entries(register: RepoRegister, project_id=None) -> list:
    """Sorted recorded rows, UNVERIFIED-marked. A query, never refuses; an
    unknown project_id yields []."""
    if not isinstance(register, RepoRegister):
        raise _err("bad_type:register")
    rows = [r for r in register.entries if project_id is None or r[1] == project_id]
    rows = sorted(rows, key=lambda r: (r[1], r[2], r[4], r[0]))
    return [_row_dict(r) for r in rows]


def render(register: RepoRegister) -> str:
    if not isinstance(register, RepoRegister):
        raise _err("bad_type:register")
    lines = []
    for pid in sorted({r[1] for r in register.entries}):
        rows = [r for r in register.entries if r[1] == pid]
        rows = sorted(rows, key=lambda r: (r[2], r[4], r[0]))
        lines.append("project %s (%d entries)" % (pid, len(rows)))
        for r in rows:
            lines.append("%s %s [%s]" % (r[2], r[3], r[5]))
    return "\n".join(lines)


def report(register: RepoRegister) -> dict:
    if not isinstance(register, RepoRegister):
        raise _err("bad_type:register")
    rows = register.entries
    return {"items": entries(register),
            "counts": {"entries": len(rows), "projects": len({r[1] for r in rows}),
                       "links": sum(1 for r in rows if r[2] == "link"),
                       "paths": sum(1 for r in rows if r[2] == "path")},
            "status": "declared_input_register_only",
            "open_verification": "UNVERIFIED",
            "resolution_performed": False,
            "fetch_performed": False,
            "evidence_verified": False,
            "boundary": BOUNDARY}


def bind_local_repositories(register, workspace, bindings):
    """Resolve declared repos to contained local Git roots and content snapshots.

    Configured origins are hashed, not published. Local snapshots do not prove
    remote availability, ownership, project identity or deliverable completion.
    """
    from pathlib import Path
    from .repo_evidence import EvidenceError, snapshot, digest
    import subprocess
    if not isinstance(register, RepoRegister):
        raise _err('bad_type:register')
    if type(bindings) is not list or len(bindings) > MAX_ENTRIES:
        raise _err('bad_type:bindings')
    workspace = Path(workspace).resolve()
    known = {row[0] for row in register.entries}
    by_id = {}
    for item in bindings:
        if type(item) is not dict or set(item) != {'entry_id', 'local_path', 'row_ids', 'project_ids'}:
            raise _err('bad_fields:binding')
        ident = item['entry_id']
        if not isinstance(ident, str) or ident not in known or ident in by_id:
            raise _err('unknown_or_duplicate:entry_id')
        if not isinstance(item['local_path'], str):
            raise _err('bad_type:local_path')
        for key in ('row_ids', 'project_ids'):
            values = item[key]
            if type(values) is not list or len(values) > 1000 or not all(isinstance(x, str) and x.strip() and len(x) <= 128 and not any(unicodedata.category(c) in FORBIDDEN_CATEGORIES for c in x) for x in values) or len(values) != len(set(values)):
                raise _err('bad_type:' + key)
        by_id[ident] = item
    rows = []
    for row in register.entries:
        ident, project, kind, value, normalized, source_ref = row
        item = by_id.get(ident)
        out = {'entry_id': ident, 'project_id': project, 'declared_kind': kind,
               'status': 'UNVERIFIED',
               'remote_verified': False, 'ownership_verified': False, 'completion_verified': False,
               'row_ids': [], 'project_ids': [project], 'snapshot': None,
               'reason': 'No local repository binding'}
        if item:
            out['row_ids'] = sorted(item['row_ids'])
            out['project_ids'] = sorted(set(item['project_ids'] + [project]))
            try:
                relative = Path(item['local_path'])
                if relative.is_absolute() or '..' in relative.parts:
                    raise EvidenceError('unsafe repository path')
                path = workspace
                for part in relative.parts:
                    path = path / part
                    if path.is_symlink():
                        raise EvidenceError('symlink repository path')
                if not path.resolve().is_relative_to(workspace) or not path.is_dir():
                    raise EvidenceError('repository path unavailable')
                snap = snapshot(path)
                out['snapshot'] = {key: snap[key] for key in ('head', 'dirty', 'tree_digest', 'status_digest', 'errors')}
                out['snapshot']['origin_configured'] = bool(snap['origin'])
                out['snapshot']['tracked_files'] = len(snap['files'])
                if not snap['errors']:
                    out['status'] = 'LOCAL-SNAPSHOT'
                    out['reason'] = 'Local Git root and tracked bytes observed; remote/project identity unverified'
            except (EvidenceError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                out['reason'] = 'Local repository inspection failed: ' + type(exc).__name__
        rows.append(out)
    return {'entries': rows, 'unbound_entry_ids': sorted(known - set(by_id)),
            'counts': {status: sum(row['status'] == status for row in rows) for status in ('LOCAL-SNAPSHOT', 'UNVERIFIED')},
            'repository_references': {row['entry_id']: {'project_ids': row['project_ids'], 'row_ids': row['row_ids']} for row in rows},
            'boundary': 'Local evidence only, operator-declared cross-references; no remote request, ownership authentication or semantic completion.'}
