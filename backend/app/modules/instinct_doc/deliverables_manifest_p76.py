"""P76|L64 - "Every project/task/module/tool/research project must produce the
following deliverables," (deliverables section header, line map v4).

Pure stdlib, deterministic, fully offline. Validates a caller-supplied
manifest declaring all 15 deliverables (P77..P91 lines) for one
project/task/module/tool/research_project. Incomplete manifests are refused
with exact codes. Declaration is not production: this module never checks a
repository, dataset, tool or paper. Per-deliverable verification lives in the
landed sibling modules (P77 repo structure, P81 deliverable-5 audit, the
P253/P255/P258 registers, P88 self-improvement); this validator consumes only
the manifest as data and records evidence refs verbatim, never resolving
them. No sibling code is imported or duplicated.
"""
from __future__ import annotations

from unicodedata import category

DELIVERABLES = (
    "a separate repository per project",
    "120+ real datasets where possible",
    "40+ external tools/services/APIs per project (Benchling, AlphaFold, etc.)",
    "200+ external tools across the program where feasible",
    "vast code, tests, verification scripts, mathematical formulas",
    "real-life data wherever possible",
    "rigorous testing and external validation",
    "benchmark comparison against the world-leading tool in the field",
    "50+ page research paper, Times New Roman, good formatting",
    "ChatGPT-as-judge review loop improving novelty, rigor, benchmark performance",
    "a new discovery/diagnosis/method/breakthrough where claimed",
    "self-improvement mechanisms per tool/module",
    "evidence of passing all requirements exactly, no thin construction",
    "scope each project at ~5 years of human time",
    "beat all relevant world benchmarks, best in world per field",
)
DELIVERABLE_COUNT = 15
KINDS = ("project", "task", "module", "tool", "research_project")
FIELDS = ("project_id", "kind", "deliverables")
DELIVERABLE_FIELDS = ("number", "evidence_ref")
TEXT_LIMITS = {"project_id": 64, "evidence_ref": 128}
_BANNED_CATEGORIES = ("Cc", "Zl", "Zp")


def _err(code: str) -> ValueError:
    return ValueError("P76:" + code)


def _text(value, name):
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


def _check_deliverable(record):
    if not isinstance(record, dict):
        raise _err("bad_type:deliverable")
    if any(k not in DELIVERABLE_FIELDS for k in record):
        raise _err("unknown_fields:deliverable")
    for name in DELIVERABLE_FIELDS:
        if name not in record:
            raise _err("empty_field:" + name)
    number = record["number"]
    if isinstance(number, bool) or not isinstance(number, int):
        raise _err("bad_type:number")
    if number < 1 or number > DELIVERABLE_COUNT:
        raise _err("number_out_of_range:number")
    evidence_ref = _text(record["evidence_ref"], "evidence_ref")
    return (number, evidence_ref)


def validate_manifest(manifest) -> dict:
    """Validate one supplied manifest. The input is never mutated; a refused
    manifest changes nothing. On success returns the canonical declaration
    rollup with deliverables sorted by number."""
    if not isinstance(manifest, dict):
        raise _err("bad_type:manifest")
    if any(k not in FIELDS for k in manifest):
        raise _err("unknown_fields:manifest")
    for name in FIELDS:
        if name not in manifest:
            raise _err("empty_field:" + name)
    project_id = _text(manifest["project_id"], "project_id")
    kind = manifest["kind"]
    if isinstance(kind, bool) or not isinstance(kind, str):
        raise _err("bad_type:kind")
    if kind not in KINDS:
        raise _err("bad_kind:" + kind)
    deliverables = manifest["deliverables"]
    if not isinstance(deliverables, list):
        raise _err("bad_type:deliverables")
    rows = [_check_deliverable(record) for record in deliverables]
    seen = set()
    for number, _ref in rows:
        if number in seen:
            raise _err("duplicate_deliverable:" + str(number))
        seen.add(number)
    missing = [n for n in range(1, DELIVERABLE_COUNT + 1) if n not in seen]
    if missing:
        raise _err("missing_deliverables:" + ",".join(str(n) for n in missing))
    return dict(
        project_id=project_id,
        kind=kind,
        deliverables=[dict(number=n, evidence_ref=ref)
                      for n, ref in sorted(rows, key=lambda r: r[0])],
        deliverable_count=DELIVERABLE_COUNT,
        complete=True,
        status="declared_manifest_only",
        evidence_verified=False,
        deliverables_produced=False,
        boundary=("Only the supplied manifest is checked. All 15 deliverables are caller "
                  "declarations; declaration is not production, evidence refs are recorded "
                  "but never resolved, and validation never touches a repository, dataset, "
                  "tool or paper."),
    )
