"""Declarative clause registry and bounded binding check for doc line P266/L212.

Offline and deterministic: no network, no files, no account use, no execution.
It checks that SUPPLIED binding declarations are present and well-formed. It does
not verify that any evidence is real, does not decide that work is complete or
good, and is not global enforcement. See docs/INSTINCT_COMPLIANCE_REGISTRY_P266_CONTRACT.md.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Iterable

REGISTRY_VERSION = "p266-l212-v1"
EVIDENCE_KINDS = ("binding_ref", "inventory_ref", "test_log_ref", "audit_ref", "other")
CLAIMS = ("complete", "in_progress", "not_started")

_P = "presence"
_N = "not_checkable_offline"


def _clause(cid: str, text: str, checkability: str, kinds: tuple[str, ...]) -> Any:
    return MappingProxyType({"id": cid, "text": text, "checkability": checkability, "required_evidence_kinds": kinds})


CLAUSES = (
    _clause("C01", "Bind every line", _P, ("binding_ref",)),
    _clause("C02", "Do not forget anything", _P, ("inventory_ref",)),
    _clause("C03", "Do not build thinly", _N, ()),
    _clause("C04", "Do not fabricate", _N, ()),
    _clause("C05", "Do not claim completion without evidence", _P, ("other",)),
    _clause("C06", "Use the user's accounts", _N, ()),
    _clause("C07", "Conduct real research", _N, ()),
    _clause("C08", "Test and verify", _P, ("test_log_ref",)),
    _clause("C09", "Beat benchmarks", _N, ()),
    _clause("C10", "Produce real discoveries", _N, ()),
    _clause("C11", "Improve novelty through ChatGPT as judge", _N, ()),
    _clause("C12", "Self-improve", _N, ()),
    _clause("C13", "Audit", _P, ("audit_ref",)),
    _clause("C14", "Then send the candy line", _N, ()),
)
_BY_ID = {c["id"]: c for c in CLAUSES}

LIMITS = {
    "evidence_truth_verified": False,
    "whole_line_fulfilment_claimed": False,
    "global_enforcement": False,
    "network": False,
    "account_use": False,
    "executes_anything": False,
}
_LINE_ORDER = ("UNBOUND", "MISSING_EVIDENCE", "OPEN", "BOUND_WITH_UNCHECKED", "UNCHECKED_ONLY", "BOUND")
_ITEM_VERDICTS = ("BOUND", "MISSING_EVIDENCE", "NOT_CHECKABLE_OFFLINE", "OPEN")


def _bound(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _text(name: str, value: Any, max_text: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-blank string")
    if len(value) > max_text:
        raise ValueError(f"{name} longer than {max_text} characters")
    return value


def _evaluate_item(raw: Any, max_evidence: int, max_text: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("each item must be a dict")
    for key in ("line_ref", "clause_id", "claim"):
        if key not in raw:
            raise ValueError(f"item missing {key}")
    line_ref = _text("line_ref", raw["line_ref"], max_text)
    clause_id = _text("clause_id", raw["clause_id"], max_text)
    clause = _BY_ID.get(clause_id)
    if clause is None:
        raise ValueError(f"unknown clause id: {clause_id}")
    claim = raw["claim"]
    if not isinstance(claim, str) or claim not in CLAIMS:
        raise ValueError(f"claim must be one of {CLAIMS}")
    evidence = raw.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("evidence must be a list")
    if len(evidence) > max_evidence:
        raise ValueError(f"more than {max_evidence} evidence entries")
    present: set[str] = set()
    for e in evidence:
        if not isinstance(e, dict) or not isinstance(e.get("kind"), str) or not isinstance(e.get("ref"), str):
            raise ValueError("evidence entries must be dicts with string kind and ref")
        if e["kind"] not in EVIDENCE_KINDS:
            raise ValueError(f"unknown evidence kind: {e['kind']}")
        if len(e["ref"]) > max_text:
            raise ValueError(f"evidence ref longer than {max_text} characters")
        if e["ref"].strip():
            present.add(e["kind"])
    required = clause["required_evidence_kinds"]
    missing = [k for k in required if k not in present]
    if clause["checkability"] == _N:
        verdict = "NOT_CHECKABLE_OFFLINE"
    elif claim != "complete":
        verdict = "OPEN"
    elif missing:
        verdict = "MISSING_EVIDENCE"
    else:
        verdict = "BOUND"
    return {
        "line_ref": line_ref,
        "clause_id": clause_id,
        "checkability": clause["checkability"],
        "claim": claim,
        "verdict": verdict,
        "evidence_kinds_present": sorted(present),
        "missing_evidence_kinds": missing if verdict == "MISSING_EVIDENCE" else [],
    }


def _line_verdict(verdicts: set[str]) -> str:
    if "MISSING_EVIDENCE" in verdicts:
        return "MISSING_EVIDENCE"
    if "OPEN" in verdicts:
        return "OPEN"
    if "NOT_CHECKABLE_OFFLINE" in verdicts:
        return "BOUND_WITH_UNCHECKED" if "BOUND" in verdicts else "UNCHECKED_ONLY"
    return "BOUND"


def check_bindings(
    items: list[dict[str, Any]],
    *,
    expected_lines: Iterable[str] | None = None,
    max_items: int = 1000,
    max_evidence: int = 50,
    max_text: int = 500,
) -> dict[str, Any]:
    """Check supplied binding declarations. Refuses (ValueError) before evaluating anything
    if the input is malformed or out of bounds."""
    _bound("max_items", max_items)
    _bound("max_evidence", max_evidence)
    _bound("max_text", max_text)
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    if len(items) > max_items:
        raise ValueError(f"more than {max_items} items")
    expected: list[str] = []
    if expected_lines is not None:
        if isinstance(expected_lines, (str, bytes)) or not isinstance(expected_lines, (list, tuple, set, frozenset)):
            raise ValueError("expected_lines must be a list of strings")
        expected = [_text("expected line", x, max_text) for x in expected_lines]
        if len(set(expected)) != len(expected):
            raise ValueError("duplicate expected line")
        if len(expected) > max_items:
            raise ValueError(f"more than {max_items} expected lines")

    rows = [_evaluate_item(x, max_evidence, max_text) for x in items]
    seen: set[tuple[str, str]] = set()
    for r in rows:
        key = (r["line_ref"], r["clause_id"])
        if key in seen:
            raise ValueError(f"duplicate binding for {key[0]} / {key[1]}")
        seen.add(key)
    rows.sort(key=lambda r: (r["line_ref"], r["clause_id"]))

    by_line: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_line.setdefault(r["line_ref"], []).append(r)
    lines = []
    for ref in sorted(set(by_line) | set(expected)):
        group = by_line.get(ref, [])
        verdict = "UNBOUND" if not group else _line_verdict({g["verdict"] for g in group})
        lines.append({"line_ref": ref, "verdict": verdict, "clause_ids": [g["clause_id"] for g in group]})
    unexpected = sorted(set(by_line) - set(expected)) if expected_lines is not None else []

    item_counts = {}
    for r in rows:
        item_counts[r["verdict"]] = item_counts.get(r["verdict"], 0) + 1
    line_counts = {}
    for ln in lines:
        line_counts[ln["verdict"]] = line_counts.get(ln["verdict"], 0) + 1
    return {
        "registry_version": REGISTRY_VERSION,
        "items": rows,
        "lines": lines,
        "unexpected_lines": unexpected,
        "counts": {"items": dict(sorted(item_counts.items())), "lines": dict(sorted(line_counts.items()))},
        "limits": dict(LIMITS),
    }
