"""Improvement-factor audit for doc line [P238|L187] (offline, stdlib only).

Doc line, verbatim: "- Improve Sugarcode x1,000,000."

The x1,000,000 is the doc's target, never this unit's claim. Given
caller-supplied before/after measurement pairs, this unit RECOMPUTES the
measured improvement factor for each metric exactly (after / before as a
Fraction), counts how many metrics actually meet the target, and reports
TARGET_NOT_MET unless the recomputed factors say otherwise. A regression
(factor below 1) and a missing evidence_ref are flags, never hidden. The
doc's improvement claim is recorded asserted=False.
"""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction

FEATURE = "improvement_factor_p238"
SOURCE_LINES = ["P238|L187"]
DOC_LINE = "- Improve Sugarcode x1,000,000."

TARGET_FACTOR = 1_000_000
MAX_METRICS = 1_024
TEXT_LIMITS = {"id": 64, "metric": 128, "evidence_ref": 128}
FIELDS = frozenset({"id", "metric", "before", "after", "evidence_ref"})

MEASURE = "improvement-factor audit: after/before recomputed exactly; x1,000,000 is a target, never a claim"
DOC_CLAIMS = [{"claim": "Sugarcode improved x1,000,000", "asserted": False}]
METHOD_LIMITS = (
    "Factors are recomputed exactly (Fraction after/before) from caller-supplied measurements. ",
    "x1,000,000 is the doc's target; this unit counts how many measured factors meet it, never asserts it. ",
    "Measurements and evidence refs are caller-declared; presence is checked, truth is not. ",
    "No benchmark is run here; regressions and missing evidence are flags, never hidden. ",
)


def _fail(code):
    raise ValueError("P238:" + code)


def _text(value, field, limit_key):
    if type(value) is not str:
        _fail("bad_type:%s" % field)
    if not value.strip():
        _fail("empty_field:%s" % field)
    if len(value) > TEXT_LIMITS[limit_key]:
        _fail("text_too_long:%s" % field)
    return value.strip()


def _exact(value, field):
    if type(value) is int and not isinstance(value, bool):
        return Fraction(value)
    if type(value) is str:
        text = value.strip()
        try:
            if "/" in text:
                num_s, den_s = text.split("/", 1)
                num, den = int(num_s), int(den_s)
                if den == 0:
                    _fail("bad_value:%s" % field)
                return Fraction(num, den)
            return Fraction(int(text))
        except ValueError:
            _fail("bad_value:%s" % field)
    _fail("bad_type:%s" % field)


def audit(metrics):
    """Recompute improvement factors. No I/O."""
    if type(metrics) is not list:
        _fail("bad_type:metrics")
    if not metrics:
        _fail("empty:metrics")
    if len(metrics) > MAX_METRICS:
        _fail("too_many:metrics")
    seen = set()
    rows = []
    meeting = 0
    for pos, m in enumerate(metrics):
        name = "metrics[%d]" % pos
        if type(m) is not dict:
            _fail("bad_type:" + name)
        for key in m:
            if key not in FIELDS:
                _fail("unknown_field:%s.%s" % (name, key))
        for field in ("id", "metric", "before", "after"):
            if field not in m:
                _fail("missing_field:%s.%s" % (name, field))
        mid = _text(m["id"], name + ".id", "id")
        if mid in seen:
            _fail("duplicate_id:%s" % mid)
        seen.add(mid)
        _text(m["metric"], name + ".metric", "metric")
        before = _exact(m["before"], name + ".before")
        after = _exact(m["after"], name + ".after")
        if before <= 0:
            _fail("bad_value:%s.before" % name)
        if after < 0:
            _fail("bad_value:%s.after" % name)
        factor = after / before
        flags = []
        if factor < 1:
            flags.append("regression")
        ref = m.get("evidence_ref")
        if ref is not None:
            _text(ref, name + ".evidence_ref", "evidence_ref")
        else:
            flags.append("missing_evidence_ref")
        if factor >= TARGET_FACTOR:
            meeting += 1
        rows.append({"id": mid, "factor": factor,
                     "meets_target": factor >= TARGET_FACTOR,
                     "flags": flags,
                     "verdict": "REVIEW" if flags else "OK"})
    blob = json.dumps([{k: (str(v) if isinstance(v, Fraction) else v)
                        for k, v in row.items()} for row in rows] +
                      [{k: (str(v) if not isinstance(v, str) else v)
                        for k, v in m.items()} for m in metrics],
                      sort_keys=True, separators=(",", ":"))
    return {"feature": FEATURE,
            "source_lines": list(SOURCE_LINES),
            "doc_line": DOC_LINE,
            "measure": MEASURE,
            "metrics_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
            "metric_rows": rows,
            "target_factor": TARGET_FACTOR,
            "metrics_meeting_target": meeting,
            "verdict": "FACTORS_RECOMPUTED" if meeting else "TARGET_NOT_MET",
            "doc_claims": [dict(c) for c in DOC_CLAIMS],
            "limits": list(METHOD_LIMITS)}


_KEYS = {"feature", "source_lines", "doc_line", "measure", "metrics_sha256",
         "metric_rows", "target_factor", "metrics_meeting_target", "verdict",
         "doc_claims", "limits"}


def verify(metrics, result):
    """Recompute from the same metrics and compare EVERY field in _KEYS;
    failed names the exact fields that differ. Deterministic, internal
    consistency only."""
    checks = ["structure", "exact_keys", "field_equality"]
    if type(result) is not dict:
        return {"verified": False, "failed": ["structure"], "checks": checks}
    if set(result) != _KEYS:
        return {"verified": False, "failed": ["exact_keys"], "checks": checks}
    expected = audit(metrics)
    failed = [key for key in sorted(_KEYS) if result[key] != expected[key]]
    return {"verified": not failed, "failed": failed, "checks": checks}


def run(metrics):
    result = audit(metrics)
    receipt = verify(metrics, result)
    return {"status": "audited" if receipt["verified"] else "verification_failed",
            "result": result, "verification": receipt}
