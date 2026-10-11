"""P253|L200 - "Output: Repository links/paths," (output-format section).

Pure stdlib, deterministic output artifact. It RECORDS supplied repository
links/paths per project, validated and deduplicated. It never resolves a link,
never fetches, never reads a filesystem, and never marks anything verified:
every recorded entry stays UNVERIFIED.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

FIELDS = ("id", "project_id", "kind", "value", "source_ref")
KINDS = ("link", "path")
TEXT_LIMITS = {"id": 64, "project_id": 64, "value": 512, "source_ref": 128}
MAX_ENTRIES = 4096

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
