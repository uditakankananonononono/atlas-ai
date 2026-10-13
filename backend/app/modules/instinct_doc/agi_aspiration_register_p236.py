"""Aspiration register for doc line [P236|L185] (offline, stdlib only).

Doc line, verbatim: "- Try to make it into AGI-like capability."

"Try to" is a process, not a result. This unit registers caller-supplied
improvement attempts and RECOMPUTES their state reconciliation
(proposed -> tested -> measured): tested requires an evidence_ref, measured
requires an evidence_ref and a metric_note, and gaps are flagged, never
papered over. AGI-like capability is recorded with asserted=False - this
unit audits attempt records; it neither achieves nor claims any capability.
"""
from __future__ import annotations

import hashlib
import json

FEATURE = "agi_aspiration_register_p236"
SOURCE_LINES = ["P236|L185"]
DOC_LINE = "- Try to make it into AGI-like capability."

MAX_ATTEMPTS = 1_024
TEXT_LIMITS = {"id": 64, "target_capability": 128, "approach": 512,
               "evidence_ref": 128, "metric_note": 256}
STATUSES = ("proposed", "tested", "measured")
FIELDS = frozenset({"id", "target_capability", "approach", "status",
                    "evidence_ref", "metric_note"})

MEASURE = "improvement-attempt register with recomputed state reconciliation; AGI never claimed"
DOC_CLAIMS = [{"claim": "AGI-like capability achieved", "asserted": False},
              {"claim": "try to make it into AGI-like capability",
               "asserted": False,
               "note": "aspiration recorded; attempts audited only"}]
METHOD_LIMITS = (
    "AGI-like capability is recorded with asserted=False; this unit audits caller-supplied attempt records only. ",
    "tested and measured are evidenced states: missing evidence or metric notes are flagged, never assumed. ",
    "No model is trained or modified here; no capability is measured by this unit itself. ",
    "Evidence refs are caller-declared; presence is checked, truth is not. ",
)


def _fail(code):
    raise ValueError("P236:" + code)


def _text(value, field, limit_key):
    if type(value) is not str:
        _fail("bad_type:%s" % field)
    if not value.strip():
        _fail("empty_field:%s" % field)
    if len(value) > TEXT_LIMITS[limit_key]:
        _fail("text_too_long:%s" % field)
    return value.strip()


def register(attempts):
    """Register attempts and recompute states. No I/O."""
    if type(attempts) is not list:
        _fail("bad_type:attempts")
    if not attempts:
        _fail("empty:attempts")
    if len(attempts) > MAX_ATTEMPTS:
        _fail("too_many:attempts")
    seen = set()
    rows = []
    counts = {}
    for pos, a in enumerate(attempts):
        name = "attempts[%d]" % pos
        if type(a) is not dict:
            _fail("bad_type:" + name)
        for key in a:
            if key not in FIELDS:
                _fail("unknown_field:%s.%s" % (name, key))
        for field in ("id", "target_capability", "approach", "status"):
            if field not in a:
                _fail("missing_field:%s.%s" % (name, field))
        aid = _text(a["id"], name + ".id", "id")
        if aid in seen:
            _fail("duplicate_id:%s" % aid)
        seen.add(aid)
        _text(a["target_capability"], name + ".target_capability",
              "target_capability")
        _text(a["approach"], name + ".approach", "approach")
        status = a["status"]
        if type(status) is not str:
            _fail("bad_type:%s.status" % name)
        if status not in STATUSES:
            _fail("bad_value:status")
        ref = a.get("evidence_ref")
        if ref is not None:
            ref = _text(ref, name + ".evidence_ref", "evidence_ref")
        metric = a.get("metric_note")
        if metric is not None:
            metric = _text(metric, name + ".metric_note", "metric_note")
        flags = []
        if status == "tested" and not ref:
            flags.append("tested_without_evidence")
        if status == "measured" and not ref:
            flags.append("measured_without_evidence")
        if status == "measured" and not metric:
            flags.append("measured_without_metric")
        if status == "proposed" and (ref or metric):
            flags.append("proposed_with_premature_evidence")
        counts[status] = counts.get(status, 0) + 1
        rows.append({"id": aid, "status": status, "flags": flags,
                     "verdict": "REVIEW" if flags else "OK"})
    issues = sum(1 for r in rows if r["verdict"] != "OK")
    canon = [{"id": r["id"], "status": r["status"], "flags": r["flags"]}
             for r in rows]
    blob = json.dumps([{**c, "input": a} for c, a in zip(canon, attempts)],
                      sort_keys=True, separators=(",", ":"), default=str)
    return {"feature": FEATURE,
            "source_lines": list(SOURCE_LINES),
            "doc_line": DOC_LINE,
            "measure": MEASURE,
            "attempts_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
            "attempt_rows": rows,
            "state_counts": counts,
            "issues": issues,
            "verdict": "ATTEMPTS_RECONCILED" if not issues else "ATTEMPTS_INCOMPLETE",
            "doc_claims": [dict(c) for c in DOC_CLAIMS],
            "limits": list(METHOD_LIMITS)}


_KEYS = {"feature", "source_lines", "doc_line", "measure", "attempts_sha256",
         "attempt_rows", "state_counts", "issues", "verdict", "doc_claims",
         "limits"}


def verify(attempts, result):
    """Re-register from the same attempts and compare EVERY field in
    _KEYS; failed names the exact fields that differ. Deterministic,
    internal consistency only."""
    checks = ["structure", "exact_keys", "field_equality"]
    if type(result) is not dict:
        return {"verified": False, "failed": ["structure"], "checks": checks}
    if set(result) != _KEYS:
        return {"verified": False, "failed": ["exact_keys"], "checks": checks}
    expected = register(attempts)
    failed = [key for key in sorted(_KEYS) if result[key] != expected[key]]
    return {"verified": not failed, "failed": failed, "checks": checks}


def run(attempts):
    result = register(attempts)
    receipt = verify(attempts, result)
    return {"status": "registered" if receipt["verified"] else "verification_failed",
            "result": result, "verification": receipt}
