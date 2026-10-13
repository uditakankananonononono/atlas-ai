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
    if type(records) is not int:
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


def bind_artifacts(register, root, bindings, *, source_reader=None):
    """Bind every declared row to local bytes and optional executed source read.

    source_reader is an operator-owned callable, separate from row declarations.
    It receives the declared source/source_ref and returns fetched source bytes.
    VERIFIED requires nonempty local/source byte equality AND parsed count match, not licensing,
    authorship, scientific adequacy or whole-project fulfillment. A supplied
    receipt/status/hash cannot select VERIFIED. Readers must enforce their own
    authorization, network destinations, timeouts and size limits.
    """
    from pathlib import Path
    import io
    from .dataset_count_reader_p254 import check_declared
    from .repo_evidence import EvidenceError, digest, safe_file
    if not isinstance(register, DatasetRegister):
        raise _err('bad_type:register')
    if type(bindings) is not list or len(bindings) > MAX_ENTRIES:
        raise _err('bad_type:bindings')
    if source_reader is not None and not callable(source_reader):
        raise _err('bad_type:source_reader')
    root_error = None
    try:
        root = Path(root).resolve()
    except Exception as exc:
        root_error = type(exc).__name__
    by_id = {}
    known = {row[0] for row in register.entries}
    for binding in bindings:
        if type(binding) is not dict or not {'entry_id', 'artifact_path', 'row_ids', 'project_ids'} <= set(binding) or set(binding) - {'entry_id', 'artifact_path', 'row_ids', 'project_ids', 'format'}:
            raise _err('bad_fields:binding')
        ident = binding['entry_id']
        if not isinstance(ident, str) or ident not in known or ident in by_id:
            raise _err('unknown_or_duplicate:entry_id')
        if not isinstance(binding['artifact_path'], str):
            raise _err('bad_type:artifact_path')
        for field in ('row_ids', 'project_ids'):
            values = binding[field]
            if type(values) is not list or len(values) > 1000 or not all(isinstance(v, str) and v.strip() and len(v) <= 128 and not any(category(c) in _BANNED_CATEGORIES for c in v) for v in values) or len(values) != len(set(values)):
                raise _err('bad_type:' + field)
        by_id[ident] = binding
    rows, cross = [], {}
    for row in register.entries:
        ident, project, dataset, declared_count, source, source_ref = row
        binding = by_id.get(ident)
        result = {'entry_id': ident, 'project_id': project, 'dataset': dataset,
                  'declared_records': declared_count, 'provenance': 'UNVERIFIED',
                  'artifact_sha256': None, 'source_sha256': None, 'source_checked': False,
                  'source_metadata_present': bool(source.strip() and source_ref.strip()),
                  'source_authenticity_verified': False, 'source_metadata_redacted': True,
                  'empty_content_match': False, 'source_bytes_match': False,
                  'record_count_status': 'UNVERIFIED', 'counted_records': None,
                  'record_count_reason': 'No supported parsed artifact count',
                  'row_ids': [], 'project_ids': [project],
                  'reference_scope': 'operator-declared references; not exhaustive discovery',
                  'reason': 'No local artifact binding'}
        if binding:
            result['row_ids'] = sorted(binding['row_ids'])
            result['project_ids'] = sorted(set(binding['project_ids'] + [project]))
            result['artifact_path_disclosed'] = False
            try:
                if root_error:
                    raise EvidenceError('root unavailable')
                artifact = safe_file(root, binding['artifact_path']).read_bytes()
                result['artifact_sha256'] = digest(artifact)
                result['artifact_bytes'] = len(artifact)
                counted = check_declared(io.BytesIO(artifact), binding.get('format'), declared_count)
                result['record_count_status'] = counted['status']
                result['counted_records'] = counted['counted_records']
                result['record_count_reason'] = counted['reason']
                result['provenance'] = 'DECLARED-ONLY' if counted['status'] == 'COUNT_MATCH' else 'UNVERIFIED'
                result['reason'] = 'Parsed count matches; source not independently read' if counted['status'] == 'COUNT_MATCH' else 'Artifact record count unverified or mismatched'
                if source_reader is not None:
                    fetched = source_reader(source, source_ref)
                    if type(fetched) is not bytes or len(fetched) > 8_000_000:
                        raise EvidenceError('source reader must return bounded bytes')
                    result['source_sha256'] = digest(fetched)
                    result['source_checked'] = True
                    result['source_bytes_match'] = fetched == artifact and bool(artifact)
                    if result['source_bytes_match'] and result['record_count_status'] == 'COUNT_MATCH':
                        result['provenance'] = 'VERIFIED'
                        result['reason'] = 'Executed source bytes match and parsed record count matches declaration'
                    else:
                        result['provenance'] = 'UNVERIFIED'
                        result['empty_content_match'] = fetched == artifact and not artifact
                        result['reason'] = 'Empty source/artifact match excluded' if result['empty_content_match'] else 'Equal bytes do not establish declared record count' if result['source_bytes_match'] else 'Executed source bytes differ from local artifact'
            except Exception as exc:
                result['provenance'] = 'UNVERIFIED'
                result['reason'] = 'Artifact/source read failed: ' + type(exc).__name__
        rows.append(result)
        if result['artifact_sha256']:
            bucket = cross.setdefault(result['artifact_sha256'], {'entry_ids': [], 'project_ids': set(), 'row_ids': set()})
            bucket['entry_ids'].append(ident)
            bucket['project_ids'].update(result['project_ids'])
            bucket['row_ids'].update(result['row_ids'])
    return {'entries': rows,
            'source_reader_injected': source_reader is not None,
            'source_authenticity_verified': False,
            'reader_boundary': 'Reader must enforce source byte budget before returning; this API cannot bound allocation inside an injected callback. Reader is operator-injected; content match does not independently authenticate the provider or authorship',
            'counts': {status: sum(row['provenance'] == status for row in rows) for status in ('VERIFIED', 'DECLARED-ONLY', 'UNVERIFIED')},
            'artifact_references': {sha: {'entry_ids': sorted(bucket['entry_ids']), 'project_ids': sorted(bucket['project_ids']), 'row_ids': sorted(bucket['row_ids'])} for sha, bucket in sorted(cross.items())},
            'unbound_entry_ids': sorted(known - set(by_id)),
            'boundary': 'Executed local/source content binding only. Parsed count match is format-scoped only, not authenticity or dataset quality; reference mappings are not semantic acceptance; private source metadata must stay private.'}
