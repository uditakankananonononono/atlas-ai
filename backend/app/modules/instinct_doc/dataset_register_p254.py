"""P254|L201 - "Output: Dataset counts and sources," (output-format section).

Pure stdlib, deterministic, fully offline. The register is an immutable
ledger of caller-supplied dataset records: it validates and stores declared
counts and named sources per project, and renders them verbatim. It never
fetches, resolves or authenticates a source, never counts real records, and
never learns anything about the world. A refused entry changes nothing.

Injection defense: every field that is interpolated into rendered text
(id, project_id, dataset, source, source_ref) rejects Unicode categories
Cc, Zl and Zp, so no accepted entry can forge, split or hide render lines.
Render line count is exactly (projects rendered) + (entries rendered).
"""
from __future__ import annotations

from dataclasses import dataclass
from unicodedata import category

FIELDS = ("id", "project_id", "dataset", "records", "source", "source_ref")
TEXT_LIMITS = {"id": 64, "project_id": 64, "dataset": 128, "source": 256, "source_ref": 256}
RECORDS_LIMIT = 10**15
MAX_ENTRIES = 4096
_BANNED_CATEGORIES = ("Cc", "Zl", "Zp")


@dataclass(frozen=True)
class DatasetRegister:
    entries: tuple = ()  # tuple of (id, project_id, dataset, records, source, source_ref)


def create_register() -> DatasetRegister:
    return DatasetRegister()


def _err(code: str) -> ValueError:
    return ValueError("P254:" + code)


def _text(entry, name):
    value = entry[name]
    if isinstance(value, bool) or not isinstance(value, str):
        raise _err("bad_type:" + name)
    if not value.strip():
        raise _err("empty_field:" + name)
    if len(value) > TEXT_LIMITS[name]:
        raise _err("text_too_long:" + name)
    for ch in value:
        if category(ch) in _BANNED_CATEGORIES:
            raise _err("unsafe_chars:" + name)
    return value


def _validate(entry) -> tuple:
    if not isinstance(entry, dict):
        raise _err("bad_type:entry")
    extra = sorted(str(k) for k in entry if k not in FIELDS)
    if extra:
        raise _err("unknown_fields:entry")
    for name in FIELDS:
        if name not in entry:
            raise _err("empty_field:" + name)
    row = tuple(_text(entry, name) for name in TEXT_LIMITS)
    records = entry["records"]
    if isinstance(records, bool) or not isinstance(records, int):
        raise _err("bad_type:records")
    if records < 0 or records > RECORDS_LIMIT:
        raise _err("count_out_of_range:records")
    return (row[0], row[1], row[2], records, row[3], row[4])


def add_entry(register, entry) -> DatasetRegister:
    """Return a NEW register with the entry posted. Inputs are never mutated."""
    if not isinstance(register, DatasetRegister):
        raise _err("bad_type:register")
    row = _validate(entry)
    if any(r[0] == row[0] for r in register.entries):
        raise _err("duplicate_id:" + row[0])
    if len(register.entries) >= MAX_ENTRIES:
        raise _err("limit_exceeded:entries")
    return DatasetRegister(register.entries + (row,))


def summary(register) -> dict:
    """Return caller-declared totals. Nothing is verified by this rollup."""
    if not isinstance(register, DatasetRegister):
        raise _err("bad_type:register")
    projects = {}
    for r in register.entries:
        p = projects.setdefault(r[1], {"entries": 0, "records": 0, "datasets": set()})
        p["entries"] += 1
        p["records"] += r[3]
        p["datasets"].add(r[2])
    return dict(
        projects={pid: dict(entries=p["entries"], records=p["records"],
                            datasets=sorted(p["datasets"]))
                  for pid, p in sorted(projects.items())},
        entry_count=len(register.entries),
        total_records=sum(r[3] for r in register.entries),
        status="declared_register_only",
        counts_verified=False,
        sources_resolved=False,
        completeness_verified=False,
        boundary=("Only supplied entries are recorded. Counts are caller declarations, "
                  "named sources are stored verbatim and never resolved or authenticated, "
                  "and an empty register does not prove the absence of datasets."),
    )


def render(register, project_id=None) -> str:
    """Render the ledger as text. Line count is invariant: one header line per
    rendered project plus one line per rendered entry, nothing else. Empty
    renders as "". Lines are joined by \\n with no trailing newline."""
    if not isinstance(register, DatasetRegister):
        raise _err("bad_type:register")
    if project_id is None:
        ids = sorted({r[1] for r in register.entries})
    else:
        if isinstance(project_id, bool) or not isinstance(project_id, str):
            raise _err("bad_type:project_id")
        if project_id not in {r[1] for r in register.entries}:
            raise _err("unknown_project:" + project_id)
        ids = [project_id]
    lines = []
    for pid in ids:
        rows = sorted((r for r in register.entries if r[1] == pid), key=lambda r: r[0])
        lines.append("project %s (%d entries, %d records)"
                     % (pid, len(rows), sum(r[3] for r in rows)))
        for r in rows:
            lines.append("%s %s %d records from %s [%s]" % (r[0], r[2], r[3], r[4], r[5]))
    return "\n".join(lines)
