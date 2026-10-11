"""P243|L191 - "Step 2: full audit round that science projects pass every
requirement, no thin building; exclude deleted doc200/230/portfolio"
(final-sequence section).

Pure stdlib, deterministic audit-round runner. MECHANISM ONLY: it consumes a
caller-supplied evidence ledger of requirement records and checks that every
non-excluded requirement carries a pass mark, applying the caller's exclusion
list (the doc's deleted doc200/230/portfolio handling). It builds no science
content, never checks that any evidence is real, and a pass verdict is not
proof that any project meets its requirements. Every recorded row stays
UNVERIFIED.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

FIELDS = ("id", "project_id", "requirement_ref", "mark", "evidence_ref")
MARKS = ("pass", "fail", "pending")
TEXT_LIMITS = {"id": 64, "project_id": 64, "requirement_ref": 128, "evidence_ref": 128}
EXCLUSION_LIMIT = 128
MAX_ENTRIES = 4096
MAX_EXCLUSIONS = 1024
FORBIDDEN_CATEGORIES = ("Cc", "Zl", "Zp")

BOUNDARY = ("Audit-round mark checker only. It verifies that supplied requirement records "
            "carry pass marks and applies the caller's exclusion list; it never judges the "
            "science, never checks that any evidence is real, and a pass verdict is not "
            "proof that any project meets its requirements.")


@dataclass(frozen=True)
class AuditLedger:
    entries: tuple = ()  # tuple of (id, project_id, requirement_ref, mark, evidence_ref)


def create_ledger() -> AuditLedger:
    return AuditLedger()


def _err(code: str) -> ValueError:
    return ValueError("P243:" + code)


def _check_text(value, name: str, limit: int) -> None:
    if isinstance(value, bool) or not isinstance(value, str):
        raise _err("bad_type:" + name)
    if not value.strip():
        raise _err("empty_field:" + name)
    if any(unicodedata.category(c) in FORBIDDEN_CATEGORIES for c in value):
        raise _err("control_chars:" + name)
    if len(value) > limit:
        raise _err("text_too_long:" + name)


def _validate(entry) -> tuple:
    if isinstance(entry, bool) or type(entry) is not dict:
        raise _err("bad_type:entry")
    if any(k not in FIELDS for k in entry):
        raise _err("unknown_fields:entry")
    for name in FIELDS:
        if name not in entry:
            raise _err("empty_field:" + name)
    for name in ("id", "project_id", "requirement_ref", "mark", "evidence_ref"):
        if isinstance(entry[name], bool) or not isinstance(entry[name], str):
            raise _err("bad_type:" + name)
    for name in ("id", "project_id", "requirement_ref", "mark", "evidence_ref"):
        if not entry[name].strip():
            raise _err("empty_field:" + name)
    for name in ("id", "project_id", "requirement_ref", "mark", "evidence_ref"):
        if any(unicodedata.category(c) in FORBIDDEN_CATEGORIES for c in entry[name]):
            raise _err("control_chars:" + name)
    for name, limit in TEXT_LIMITS.items():
        if len(entry[name]) > limit:
            raise _err("text_too_long:" + name)
    if entry["mark"] not in MARKS:
        raise _err("bad_mark:" + entry["mark"])
    return (entry["id"], entry["project_id"], entry["requirement_ref"], entry["mark"],
            entry["evidence_ref"])


def add_entry(ledger: AuditLedger, entry) -> AuditLedger:
    if not isinstance(ledger, AuditLedger):
        raise _err("bad_type:ledger")
    row = _validate(entry)
    eid, project_id, requirement_ref, _, _ = row
    if any(r[0] == eid for r in ledger.entries):
        raise _err("duplicate_id:" + eid)
    for r in ledger.entries:
        if r[1] == project_id and r[2] == requirement_ref:
            raise _err("duplicate_requirement:" + r[0])
    if len(ledger.entries) >= MAX_ENTRIES:
        raise _err("limit_exceeded:entries")
    return AuditLedger(ledger.entries + (row,))


def _exclusion_set(exclusions) -> frozenset:
    if exclusions is None:
        return frozenset()
    if isinstance(exclusions, (str, bytes)) or not isinstance(exclusions, (list, tuple, frozenset, set)):
        raise _err("bad_type:exclusions")
    if len(exclusions) > MAX_EXCLUSIONS:
        raise _err("limit_exceeded:exclusions")
    seen = set()
    for x in exclusions:
        _check_text(x, "exclusion", EXCLUSION_LIMIT)
        if x in seen:
            raise _err("duplicate_exclusion:" + x)
        seen.add(x)
    return frozenset(seen)


def _rows(ledger: AuditLedger, exclusions):
    excl = _exclusion_set(exclusions)
    active = sorted((r for r in ledger.entries if r[2] not in excl),
                    key=lambda r: (r[1], r[2], r[0]))
    excluded = sorted((r for r in ledger.entries if r[2] in excl),
                      key=lambda r: (r[1], r[2], r[0]))
    unmatched = sorted(excl - {r[2] for r in ledger.entries})
    return active, excluded, unmatched


def _row_dict(row, excluded: bool) -> dict:
    return {"id": row[0], "project_id": row[1], "requirement_ref": row[2],
            "mark": row[3], "evidence_ref": row[4], "excluded": excluded,
            "verification": "UNVERIFIED"}


def items(ledger: AuditLedger, exclusions=()) -> list:
    """Sorted row dicts, active rows first then excluded, UNVERIFIED-marked."""
    if not isinstance(ledger, AuditLedger):
        raise _err("bad_type:ledger")
    active, excluded, _ = _rows(ledger, exclusions)
    return [_row_dict(r, False) for r in active] + [_row_dict(r, True) for r in excluded]


def report(ledger: AuditLedger, exclusions=()) -> dict:
    if not isinstance(ledger, AuditLedger):
        raise _err("bad_type:ledger")
    active, excluded, unmatched = _rows(ledger, exclusions)
    failing = sorted(r[0] for r in active if r[3] == "fail")
    pending = sorted(r[0] for r in active if r[3] == "pending")
    verdict = "pass" if active and not failing and not pending else "fail"
    return {"verdict": verdict,
            "counts": {"entries": len(ledger.entries), "active": len(active),
                       "excluded": len(excluded),
                       "passed": sum(1 for r in ledger.entries if r[3] == "pass"),
                       "failed": sum(1 for r in ledger.entries if r[3] == "fail"),
                       "pending": sum(1 for r in ledger.entries if r[3] == "pending"),
                       "unmatched_exclusions": len(unmatched)},
            "failing": failing,
            "pending": pending,
            "excluded": sorted(r[0] for r in excluded),
            "unmatched_exclusions": unmatched,
            "items": [_row_dict(r, False) for r in active]
                     + [_row_dict(r, True) for r in excluded],
            "status": "declared_marks_checked_only",
            "marks_truth_verified": False,
            "science_content_built": False,
            "evidence_verified": False,
            "open_verification": "UNVERIFIED",
            "boundary": BOUNDARY}


def render(ledger: AuditLedger, exclusions=()) -> str:
    if not isinstance(ledger, AuditLedger):
        raise _err("bad_type:ledger")
    active, excluded, unmatched = _rows(ledger, exclusions)
    failing = sum(1 for r in active if r[3] == "fail")
    pending = sum(1 for r in active if r[3] == "pending")
    verdict = "pass" if active and not failing and not pending else "fail"
    lines = ["audit round verdict %s (%d active, %d excluded)" % (verdict, len(active), len(excluded))]
    lines += ["%s %s %s [%s]" % (r[1], r[2], r[3], r[4]) for r in active]
    lines += ["excluded %s %s %s [%s]" % (r[1], r[2], r[3], r[4]) for r in excluded]
    lines += ["unmatched exclusion %s" % x for x in unmatched]
    return "\n".join(lines)
