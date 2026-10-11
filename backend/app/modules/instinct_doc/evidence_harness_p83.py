"""P83|L71 - "Deliverable 7: rigorous testing and external validation,"
(deliverables section).

Pure stdlib, offline, deterministic evidence harness. It RECORDS caller-supplied
test/verification/external-validation evidence entries per project and checks
each project against caller-declared required evidence kinds. It never runs a
test, never executes anything, never makes a live external call: external-
validation claims are recorded and marked UNVERIFIED whether or not a receipt
string is supplied - a receipt is recorded, never verified. Honesty semantics
(the VERIFIED/UNVERIFIED label vocabulary) are COMPOSED from the landed P65
claim-status module, not duplicated.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from app.reports.claim_status import DEFAULT_LABELS as CLAIM_LABELS  # P65 composition

FIELDS = ("id", "project_id", "kind", "ref", "receipt")
KINDS = ("test_run", "verification_run", "external_validation")
DEFAULT_REQUIRED_KINDS = ("test_run", "verification_run")
TEXT_LIMITS = {"id": 64, "project_id": 64, "ref": 256, "receipt": 256}
MAX_ENTRIES = 4096
FORBIDDEN_CATEGORIES = ("Cc", "Zl", "Zp")
UNVERIFIED = "UNVERIFIED"
assert UNVERIFIED in CLAIM_LABELS  # composed label must stay in the P65 vocabulary

BOUNDARY = ("Declared-evidence harness only. It records supplied test, verification and "
            "external-validation evidence and checks per-project coverage of caller-declared "
            "required kinds. It never executes evidence, never makes a live external call and "
            "never verifies a receipt, so every claim stays UNVERIFIED and a complete verdict "
            "is not proof that any project was rigorously tested.")


@dataclass(frozen=True)
class EvidenceHarness:
    entries: tuple = ()  # tuple of (id, project_id, kind, ref, receipt_or_None)


def create_harness() -> EvidenceHarness:
    return EvidenceHarness()


def _err(code: str) -> ValueError:
    return ValueError("P83:" + code)


def _validate(entry) -> tuple:
    if isinstance(entry, bool) or type(entry) is not dict:
        raise _err("bad_type:entry")
    if any(k not in FIELDS for k in entry):
        raise _err("unknown_fields:entry")
    for name in ("id", "project_id", "kind", "ref"):
        if name not in entry:
            raise _err("empty_field:" + name)
    for name in ("id", "project_id", "kind", "ref"):
        if isinstance(entry[name], bool) or not isinstance(entry[name], str):
            raise _err("bad_type:" + name)
    receipt = entry.get("receipt")
    if receipt is not None and (isinstance(receipt, bool) or not isinstance(receipt, str)):
        raise _err("bad_type:receipt")
    for name in ("id", "project_id", "kind", "ref"):
        if not entry[name].strip():
            raise _err("empty_field:" + name)
    if receipt is not None and not receipt.strip():
        receipt = None  # a blank receipt is no receipt
    for name in ("id", "project_id", "kind", "ref"):
        if any(unicodedata.category(c) in FORBIDDEN_CATEGORIES for c in entry[name]):
            raise _err("control_chars:" + name)
    if receipt is not None and any(unicodedata.category(c) in FORBIDDEN_CATEGORIES for c in receipt):
        raise _err("control_chars:receipt")
    for name, limit in TEXT_LIMITS.items():
        value = entry.get(name) if name != "receipt" else receipt
        if value is not None and len(value) > limit:
            raise _err("text_too_long:" + name)
    if entry["kind"] not in KINDS:
        raise _err("bad_kind:" + entry["kind"])
    return (entry["id"], entry["project_id"], entry["kind"], entry["ref"], receipt)


def add_entry(harness: EvidenceHarness, entry) -> EvidenceHarness:
    if not isinstance(harness, EvidenceHarness):
        raise _err("bad_type:harness")
    row = _validate(entry)
    eid, project_id, kind, ref, _ = row
    if any(r[0] == eid for r in harness.entries):
        raise _err("duplicate_id:" + eid)
    for r in harness.entries:
        if r[1] == project_id and r[2] == kind and r[3] == ref:
            raise _err("duplicate_entry:" + r[0])
    if len(harness.entries) >= MAX_ENTRIES:
        raise _err("limit_exceeded:entries")
    return EvidenceHarness(harness.entries + (row,))


def _required(required_kinds) -> tuple:
    if required_kinds is None:
        return DEFAULT_REQUIRED_KINDS
    if isinstance(required_kinds, (str, bytes)) or not isinstance(required_kinds, (list, tuple)):
        raise _err("bad_type:required_kinds")
    if not required_kinds:
        raise _err("empty_field:required_kinds")
    seen = set()
    for k in required_kinds:
        if isinstance(k, bool) or not isinstance(k, str):
            raise _err("bad_type:required_kind")
        if k not in KINDS:
            raise _err("bad_required_kind:" + k)
        if k in seen:
            raise _err("duplicate_required_kind:" + k)
        seen.add(k)
    return tuple(required_kinds)


def _row_dict(row) -> dict:
    return {"id": row[0], "project_id": row[1], "kind": row[2], "ref": row[3],
            "receipt_present": row[4] is not None, "verification": UNVERIFIED}


def items(harness: EvidenceHarness) -> list:
    """Sorted recorded rows, UNVERIFIED-marked."""
    if not isinstance(harness, EvidenceHarness):
        raise _err("bad_type:harness")
    return [_row_dict(r) for r in sorted(harness.entries, key=lambda r: (r[1], r[2], r[3], r[0]))]


def _projects(harness: EvidenceHarness, required: tuple) -> list:
    out = []
    for pid in sorted({r[1] for r in harness.entries}):
        rows = [r for r in harness.entries if r[1] == pid]
        present = {r[2] for r in rows}
        missing = [k for k in required if k not in present]
        out.append({"project_id": pid,
                    "kinds_present": sorted(present),
                    "missing": missing,
                    "complete": not missing,
                    "entries": len(rows)})
    return out


def report(harness: EvidenceHarness, required_kinds=None) -> dict:
    if not isinstance(harness, EvidenceHarness):
        raise _err("bad_type:harness")
    required = _required(required_kinds)
    projects = _projects(harness, required)
    ev = [r for r in harness.entries if r[2] == "external_validation"]
    return {"verdict": "complete" if projects and all(p["complete"] for p in projects)
                       else "incomplete",
            "counts": {"projects": len(projects), "entries": len(harness.entries),
                       "complete_projects": sum(1 for p in projects if p["complete"]),
                       "incomplete_projects": sum(1 for p in projects if not p["complete"]),
                       "external_validation_claims": len(ev),
                       "external_validation_with_receipt": sum(1 for r in ev if r[4] is not None)},
            "projects": projects,
            "items": items(harness),
            "required_kinds": list(required),
            "status": "declared_evidence_register_only",
            "evidence_executed": False,
            "external_calls_made": False,
            "receipts_verified": False,
            "open_verification": UNVERIFIED,
            "claim_labels": sorted(CLAIM_LABELS),
            "boundary": BOUNDARY}


def render(harness: EvidenceHarness, required_kinds=None) -> str:
    if not isinstance(harness, EvidenceHarness):
        raise _err("bad_type:harness")
    required = _required(required_kinds)
    projects = _projects(harness, required)
    verdict = "complete" if projects and all(p["complete"] for p in projects) else "incomplete"
    lines = ["evidence harness verdict %s (%d projects, %d entries)"
             % (verdict, len(projects), len(harness.entries))]
    for p in projects:
        lines.append("project %s %s missing %s entries %d"
                     % (p["project_id"], "complete" if p["complete"] else "incomplete",
                        ",".join(p["missing"]) if p["missing"] else "none", p["entries"]))
    return "\n".join(lines)
