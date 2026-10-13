"""Superlative-claim audit for doc line [P239|L188] (offline, stdlib only).

Doc line, verbatim: "- Make both the best in the world."

"Best in the world" is a superlative: unverifiable by construction - no
finite caller-supplied comparison set covers the world, and no ranking is
asserted here, ever. This unit records the claim with asserted=False and
verifiable=False, audits caller-supplied comparison records (subject,
competitor, metric, evidence_ref), and RECOMPUTES coverage: which subjects
have comparisons, how many, and which records lack evidence. The verdict is
always SUPERLATIVE_UNVERIFIABLE - it can never become "best".
"""
from __future__ import annotations

import hashlib
import json

FEATURE = "superlative_claim_p239"
SOURCE_LINES = ["P239|L188"]
DOC_LINE = "- Make both the best in the world."

MAX_COMPARISONS = 1_024
TEXT_LIMITS = {"id": 64, "subject": 128, "competitor": 128, "metric": 128,
               "evidence_ref": 128}
FIELDS = frozenset({"id", "subject", "competitor", "metric", "evidence_ref"})

MEASURE = "superlative-claim audit: claim recorded unverifiable; comparison coverage recomputed"
DOC_CLAIMS = [{"claim": "both are the best in the world",
               "asserted": False, "verifiable": False,
               "note": "a superlative over an open world; comparison coverage is recomputed, rank never asserted"}]
METHOD_LIMITS = (
    "The superlative is recorded with asserted=False, verifiable=False; the verdict can never become 'best'. ",
    "Comparisons are caller-declared; missing evidence is flagged, truth is not judged. ",
    "Coverage (subjects and counts) is recomputed from the records on every call. ",
)


def _fail(code):
    raise ValueError("P239:" + code)


def _text(value, field, limit_key):
    if type(value) is not str:
        _fail("bad_type:%s" % field)
    if not value.strip():
        _fail("empty_field:%s" % field)
    if len(value) > TEXT_LIMITS[limit_key]:
        _fail("text_too_long:%s" % field)
    return value.strip()


def audit(comparisons):
    """Recompute comparison coverage. No I/O."""
    if type(comparisons) is not list:
        _fail("bad_type:comparisons")
    if not comparisons:
        _fail("empty:comparisons")
    if len(comparisons) > MAX_COMPARISONS:
        _fail("too_many:comparisons")
    seen = set()
    rows = []
    subjects = set()
    for pos, c in enumerate(comparisons):
        name = "comparisons[%d]" % pos
        if type(c) is not dict:
            _fail("bad_type:" + name)
        for key in c:
            if key not in FIELDS:
                _fail("unknown_field:%s.%s" % (name, key))
        for field in ("id", "subject", "competitor", "metric"):
            if field not in c:
                _fail("missing_field:%s.%s" % (name, field))
        cid = _text(c["id"], name + ".id", "id")
        if cid in seen:
            _fail("duplicate_id:%s" % cid)
        seen.add(cid)
        subject = _text(c["subject"], name + ".subject", "subject")
        _text(c["competitor"], name + ".competitor", "competitor")
        _text(c["metric"], name + ".metric", "metric")
        flags = []
        ref = c.get("evidence_ref")
        if ref is not None:
            _text(ref, name + ".evidence_ref", "evidence_ref")
        else:
            flags.append("missing_evidence_ref")
        subjects.add(subject)
        rows.append({"id": cid, "subject": subject, "flags": flags,
                     "verdict": "REVIEW" if flags else "OK"})
    issues = sum(1 for r in rows if r["verdict"] != "OK")
    blob = json.dumps(rows + comparisons, sort_keys=True,
                      separators=(",", ":"), default=str)
    return {"feature": FEATURE,
            "source_lines": list(SOURCE_LINES),
            "doc_line": DOC_LINE,
            "measure": MEASURE,
            "comparisons_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
            "comparison_rows": rows,
            "subjects_covered": sorted(subjects),
            "comparisons": len(rows),
            "issues": issues,
            "verdict": "SUPERLATIVE_UNVERIFIABLE",
            "doc_claims": [dict(c) for c in DOC_CLAIMS],
            "limits": list(METHOD_LIMITS)}


_KEYS = {"feature", "source_lines", "doc_line", "measure",
         "comparisons_sha256", "comparison_rows", "subjects_covered",
         "comparisons", "issues", "verdict", "doc_claims", "limits"}


def verify(comparisons, result):
    """Recompute from the same comparisons and compare EVERY field in _KEYS;
    failed names the exact fields that differ. Deterministic, internal
    consistency only."""
    checks = ["structure", "exact_keys", "field_equality"]
    if type(result) is not dict:
        return {"verified": False, "failed": ["structure"], "checks": checks}
    if set(result) != _KEYS:
        return {"verified": False, "failed": ["exact_keys"], "checks": checks}
    expected = audit(comparisons)
    failed = [key for key in sorted(_KEYS) if result[key] != expected[key]]
    return {"verified": not failed, "failed": failed, "checks": checks}


def run(comparisons):
    result = audit(comparisons)
    receipt = verify(comparisons, result)
    return {"status": "audited" if receipt["verified"] else "verification_failed",
            "result": result, "verification": receipt}
